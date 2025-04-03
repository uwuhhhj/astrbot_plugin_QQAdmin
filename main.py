
import random
from typing import Dict

import astrbot.api.message_components as Comp
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


superusers = []


BAN_ME_QUOTES: list=[
    "还真有人有这种奇怪的要求",
    "满足你",
    "静一会也挺好的",
    "是你自己要求的哈！",
    "行，你去静静",
    "好好好，禁了",
    "主人你没事吧？"
]


@register("astrbot_plugin_admin", "Zhalslar", "帮助你管理群聊", "1.0.0", "https://github.com/Zhalslar/astrbot_plugin_admin")
class AdminPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.superusers = config.get('superusers')
        self.ban_rand_time_min=config.get('ban_rand_time_min') # 随机禁言时的最小时长(秒)
        self.ban_rand_time_max =config.get('ban_rand_time_max') # 随机禁言时的最大时长(秒)




    @staticmethod
    async def get_nickname(event: AiocqhttpMessageEvent, user_id) -> str:
        """获取指定群友的群昵称或Q名"""
        client = event.bot
        group_id = event.get_group_id()
        all_info = await client.get_group_member_info(
            group_id=int(group_id),
            user_id=int(user_id)
        )
        nickname = all_info.get('card') or all_info.get('nickname')
        return nickname


    @staticmethod
    def get_ats(event: AiocqhttpMessageEvent) -> list[str]:
        """获取被at者们的id列表"""
        messages = event.get_messages()
        self_id = event.get_self_id()
        return [str(seg.qq) for seg in messages if (isinstance(seg, Comp.At) and str(seg.qq) != self_id)]


    @staticmethod
    async def check_permissions(event: AiocqhttpMessageEvent, user_id) -> int:
        """获取指定用户的权限等级，等级0到3，对应权限分别开放到超管、群主、管理员、成员"""
        client = event.bot
        group_id = event.get_group_id()
        if str(user_id) in superusers:
            return 0
        all_info = await client.get_group_member_info(
            group_id=int(group_id),
            user_id=int(user_id),
            no_cache=True
        )  # 使用缓存提高效率
        role = all_info.get('role', 'unknown')
        role_to_level: Dict[str, int] = {'owner': 1, 'admin': 2, 'member': 3}
        level = role_to_level.get(role, 4)  # 默认值4，适用于未知角色
        print(f"当前用户权限等级：{level}")
        return level

    async def perm_block(
            self,
            event: AiocqhttpMessageEvent,
            user_level: int = 2,  # 默认用户权限等级为2（管理员）
            bot_level: int = 2,  # 默认机器人权限等级为2（管理员）
    ) -> str | None:
        """
        执行权限检查。
        用户和机器人的权限等级默认为2（管理员权限）。
        如果权限不足，返回提示信息；否则返回None表示权限检查通过。
        """

        sender_id = event.get_sender_id()
        self_id = event.get_self_id()

        # 检查用户的权限等级
        user_perm = await self.check_permissions(event, user_id=sender_id)
        at_ids = self.get_ats(event)

        if user_perm > user_level:
            return '你没这权限'

        # 检查bot的权限等级
        bot_perm = await self.check_permissions(event, user_id=self_id)
        if bot_perm > bot_level:
            return '我可没这权限'

        # 获取被at者的权限等级
        if at_ids:
            for aid in at_ids:
                at_perm = await self.check_permissions(event,user_id=aid)
                if bot_perm >= at_perm:
                    return '我只能动身份比我低的人'

        return None  # 权限检查通过，未被阻塞


    @filter.command("禁言")
    async def set_group_ban(self, event: AiocqhttpMessageEvent, time:int=None):
        """禁言 60 @user """
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        ban_time = time or random.randint(self.ban_rand_time_min, self.ban_rand_time_max)
        tids = self.get_ats(event)
        for tid in tids:
            await client.set_group_ban(
                group_id=int(group_id),
                user_id=int(tid),
                duration=ban_time
            )

    @filter.command("禁我")
    async def set_group_ban_me(self, event: AiocqhttpMessageEvent, time: int = None):
        """禁我 60"""
        result = await self.perm_block(event, user_level=3, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        time = time or random.randint(self.ban_rand_time_min, self.ban_rand_time_max)
        await client.set_group_ban(
            group_id=int(group_id),
            user_id=int(send_id),
            duration=time
        )
        yield event.plain_result(random.choice(BAN_ME_QUOTES))


    @filter.command("解禁")
    async def cancel_group_ban(self, event: AiocqhttpMessageEvent):
        """解禁@user"""
        result = await self.perm_block(event, user_level=3, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            await client.set_group_ban(
                group_id=int(group_id),
                user_id=int(tid),
                duration=0
            )


    @filter.command("全体禁言")
    async def set_group_whole_ban(self, event: AiocqhttpMessageEvent):
        """全体禁言"""
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_whole_ban(group_id=int(group_id), enable=True)
        yield event.plain_result("已开启全员禁言")


    @filter.command("解除全体禁言")
    async def cancel_group_whole_ban(self, event: AiocqhttpMessageEvent):
        """解除全体禁言"""
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_whole_ban(group_id=int(group_id), enable=False)
        yield event.plain_result("已解除全员禁言")


    @filter.command("改名")
    async def set_group_card(self, event: AiocqhttpMessageEvent, target_card:str=None):
        """改名 xxx @user"""
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        if not target_card:
            yield event.plain_result("想要什么新昵称？")
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_card(
                group_id=int(group_id),
                user_id=int(tid),
                card=target_card
            )
            chain = [
                Comp.Plain(text="已将"),
                Comp.At(qq=tid),
                Comp.Plain(text=f"的群昵称改为\n【{target_card}】")
            ]
            yield event.chain_result(chain)


    @filter.command("改我")
    async def set_group_card_me(self, event: AiocqhttpMessageEvent, target_card:str=None):
        """改我 xxx"""
        result = await self.perm_block(event, user_level=3, bot_level=1)
        if result:
            yield event.plain_result(result)
            return
        if not target_card:
            yield event.plain_result("想要什么新昵称？")

        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        await client.set_group_card(
            group_id=int(group_id),
            user_id=int(send_id),
            card=target_card
        )
        yield event.plain_result(f"已将你的群昵称改为【{target_card}】")


    @filter.command("头衔")
    async def set_group_special_title(self, event: AiocqhttpMessageEvent, new_title:str=None):
        """头衔 xxx @user"""
        result = await self.perm_block(event, user_level=2, bot_level=1)
        if result:
            yield event.plain_result(result)
            return
        if not new_title:
            yield event.plain_result("想要什么头衔？")
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_special_title(
                group_id=int(group_id),
                user_id=int(tid),
                special_title=new_title,
                duration=-1
            )
            chain = [
                Comp.Plain(text="已将"),
                Comp.At(qq=tid),
                Comp.Plain(text=f"的头衔改为\n【{new_title}】")
            ]
            yield event.chain_result(chain)


    @filter.command("我要头衔")
    async def set_group_special_title_me(self, event: AiocqhttpMessageEvent, new_title:str=None):
        """我要头衔 xxx"""
        result = await self.perm_block(event, user_level=3, bot_level=1)
        if result:
            yield event.plain_result(result)
            return
        if not new_title:
            yield event.plain_result("想要什么头衔？")
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        await client.set_group_special_title(
            group_id=int(group_id),
            user_id=int(send_id),
            special_title=new_title,
            duration=-1
        )
        yield event.plain_result(f"已将你的头衔改为\n【{new_title}】")


    @filter.command("踢了")
    async def set_group_kick(self, event: AiocqhttpMessageEvent):
        """踢了@user"""
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result(f"想踢了谁？")
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            await client.set_group_kick(
                group_id=int(group_id),
                user_id=int(tid),
                reject_add_request=False)
            yield event.plain_result(f"已将【{tid}-{target_name}】踢出本群")


    @filter.command("拉黑")
    async def set_group_block(self, event: AiocqhttpMessageEvent):
        """拉黑 @user"""
        result = await self.perm_block(event, user_level=2, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result(f"想拉黑谁？")
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            await client.set_group_kick(
                group_id=int(group_id),
                user_id=int(tid),
                reject_add_request=True)
            yield event.plain_result(f"已将【{tid}-{target_name}】踢出本群并拉黑!")


    @filter.command("设置管理员")
    async def set_group_admin(self, event: AiocqhttpMessageEvent):
        """设置管理员@user"""
        result = await self.perm_block(event, user_level=1, bot_level=1)
        if result:
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result(f"想设置谁为管理员？")
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_admin(
                group_id=int(group_id),
                user_id=int(tid),
                enable=True
            )
            chain = [
                Comp.At(qq=tid),
                Comp.Plain(text='你已被设置为管理员')
            ]
            yield event.chain_result(chain)


    @filter.command("取消管理员")
    async def cancel_group_admin(self, event: AiocqhttpMessageEvent):
        """取消管理员@user"""
        result = await self.perm_block(event, user_level=1, bot_level=1)
        if result:
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result(f"想取消谁的管理员身份？")
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_admin(
                group_id=int(group_id),
                user_id=int(tid),
                enable=False
            )
            chain = [
                Comp.At(qq=tid),
                Comp.Plain(text='你的管理员身份已被取消')
            ]
            yield event.chain_result(chain)


    @filter.command("设精")
    async def set_essence_msg(self, event: AiocqhttpMessageEvent):
        """将引用消息添加到群精华"""
        result = await self.perm_block(event, user_level=3, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        messages = event.get_messages()
        if isinstance(messages[0], Comp.Reply):
            client = event.bot
            reply_message_id = event.message_obj.message[0].id
            await client.set_essence_msg(message_id=int(reply_message_id))
            yield event.plain_result(f'添加了')

    @filter.command("取精")
    async def cancel_essence_msg(self, event: AiocqhttpMessageEvent):
        """将引用消息移出群精华"""
        result = await self.perm_block(event, user_level=3, bot_level=2)
        if result:
            yield event.plain_result(result)
            return
        messages = event.get_messages()
        if isinstance(messages[0], Comp.Reply):
            client = event.bot
            reply_message_id = event.message_obj.message[0].id
            await client.delete_essence_msg(message_id=int(reply_message_id))
            yield event.plain_result(f'取消了')

    @filter.command("撤回")
    async def delete_msg(self, event: AiocqhttpMessageEvent):
        """撤回 引用的消息 和 发送的消息"""
        messages = event.get_messages()
        if isinstance(messages[0], Comp.Reply):
            client = event.bot
            reply_message_id = event.message_obj.message[0].id
            message_id = event.message_obj.message_id
            await client.delete_msg(message_id=int(reply_message_id))
            await client.delete_msg(message_id=int(message_id))









