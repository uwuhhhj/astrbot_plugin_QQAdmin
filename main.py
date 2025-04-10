import asyncio
import random
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import aiohttp
import astrbot.api.message_components as Comp
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


BAN_ME_QUOTES: List[str] = [
    "还真有人有这种奇怪的要求",
    "满足你",
    "静一会也挺好的",
    "是你自己要求的哈！",
    "行，你去静静",
    "好好好，禁了",
    "主人你没事吧？",
]
PLUGIN_DIR = Path(__file__).resolve().parent
TEMP_DIR = PLUGIN_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


@register(
    "astrbot_plugin_QQAdmin",
    "Zhalslar",
    "帮助你管理群聊",
    "2.0.1",
    "https://github.com/Zhalslar/astrbot_plugin_QQAdmin",
)
class AdminPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.superusers: list[str] = config.get("superusers", [])

        ban_time_setting: Dict = config.get("ban_time_setting", {})
        self.ban_rand_time_min: int = ban_time_setting.get(
            "ban_rand_time_min", 30
        )  # 随机禁言时的最小时长(秒)
        self.ban_rand_time_max: int = ban_time_setting.get(
            "ban_rand_time_max", 300
        )  # 随机禁言时的最大时长(秒)

        self.night_start_time: str = config.get(
            "night_start_time", "23:30"
        )  # 默认的宵禁开始时间
        self.night_end_time: str = config.get(
            "night_end_time", "6:00"
        )  # 默认的宵禁结束时间

        self.perms: Dict = config.get("perm_setting", {})  # 权限配置

        if datetime.datetime.today().weekday() == 3:
            self.print_logo() # 星期四打印 Logo，哈哈哈

    def print_logo(self):
        """打印欢迎 Logo"""
        logo = r"""
 ________  __                  __            __
|        \|  \                |  \          |  \
 \$$$$$$$$| $$____    ______  | $$  _______ | $$  ______    ______
    /  $$ | $$    \  |      \ | $$ /       \| $$ |      \  /      \
   /  $$  | $$$$$$$\  \$$$$$$\| $$|  $$$$$$$| $$  \$$$$$$\|  $$$$$$\
  /  $$   | $$  | $$ /      $$| $$ \$$    \ | $$ /      $$| $$   \$$
 /  $$___ | $$  | $$|  $$$$$$$| $$ _\$$$$$$\| $$|  $$$$$$$| $$
|  $$    \| $$  | $$ \$$    $$| $$|       $$| $$ \$$    $$| $$
 \$$$$$$$$ \$$   \$$  \$$$$$$$ \$$ \$$$$$$$  \$$  \$$$$$$$ \$$

        """
        print("\033[92m" + logo + "\033[0m")  # 绿色文字
        print("\033[94m欢迎使用群管插件！\033[0m")  # 蓝色文字


    @staticmethod
    async def get_nickname(event: AiocqhttpMessageEvent, user_id) -> str:
        """获取指定群友的群昵称或Q名"""
        client = event.bot
        group_id = event.get_group_id()
        all_info = await client.get_group_member_info(
            group_id=int(group_id), user_id=int(user_id)
        )
        nickname = all_info.get("card") or all_info.get("nickname")
        return nickname

    @staticmethod
    def get_ats(event: AiocqhttpMessageEvent) -> list[str]:
        """获取被at者们的id列表"""
        messages = event.get_messages()
        self_id = event.get_self_id()
        return [
            str(seg.qq)
            for seg in messages
            if (isinstance(seg, Comp.At) and str(seg.qq) != self_id)
        ]

    async def get_perm_level(
        self, event: AiocqhttpMessageEvent, user_id: str | int
    ) -> int:
        """获取指定用户的权限等级，等级0,1,2,3，对应权限分别开放到超管、群主、管理员、成员"""
        client = event.bot
        group_id = event.get_group_id()
        if str(user_id) in self.superusers:
            return 0
        all_info = await client.get_group_member_info(
            group_id=int(group_id), user_id=int(user_id), no_cache=True
        )  # 使用缓存提高效率
        role = all_info.get("role", "unknown")
        role_to_level: Dict[str, int] = {"owner": 1, "admin": 2, "member": 3}
        level = role_to_level.get(role, 4)  # 默认值4，适用于未知角色
        print(f"当前用户权限等级：{level}")
        return level

    @staticmethod
    def perm_to_level(user_perm):
        """权限到等级的映射"""
        perm_to_level = {"超管": 0, "群主": 1, "管理员": 2, "成员": 3}
        if user_perm not in perm_to_level:
            return 4

        # 获取对应的等级
        user_level = perm_to_level[user_perm]
        return user_level

    async def perm_block(
        self,
        event: AiocqhttpMessageEvent,
        user_perm: str | None = "管理员",
        bot_perm: str | None = "管理员",
    ) -> str | None:
        """
        执行权限检查。
        如果权限不足，返回提示信息；否则返回None表示权限检查通过。
        """
        user_level = self.perm_to_level(user_perm)
        bot_level = self.perm_to_level(bot_perm)

        sender_id = event.get_sender_id()
        self_id = event.get_self_id()

        # 检查用户的权限等级
        user_level = await self.get_perm_level(event, user_id=sender_id)
        at_ids = self.get_ats(event)

        if user_level > user_level:
            return "你没这权限"

        # 检查bot的权限等级
        bot_level = await self.get_perm_level(event, user_id=self_id)
        if bot_level > bot_level:
            return "我可没这权限"

        # 获取被at者的权限等级
        if at_ids:
            for aid in at_ids:
                at_level = await self.get_perm_level(event, user_id=aid)
                if bot_level >= at_level:
                    return "我动不了这人"

        return None  # 权限检查通过，未被阻塞

    @filter.command("禁言")
    async def set_ban(self, event: AiocqhttpMessageEvent, time: int | None = None):
        """禁言 60 @user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_ban_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        ban_time = time or random.randint(
            self.ban_rand_time_min, self.ban_rand_time_max
        )
        tids = self.get_ats(event)
        for tid in tids:
            await client.set_group_ban(
                group_id=int(group_id), user_id=int(tid), duration=ban_time
            )
        event.stop_event()

    @filter.command("禁我")
    async def set_ban_me(self, event: AiocqhttpMessageEvent, time: int | None = None):
        """禁我 60"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_ban_me_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        time = time or random.randint(self.ban_rand_time_min, self.ban_rand_time_max)
        try:
            await client.set_group_ban(
                group_id=int(group_id), user_id=int(send_id), duration=time
            )
            yield event.plain_result(random.choice(BAN_ME_QUOTES))
        except:  # noqa: E722
            yield event.plain_result("我可禁言不了你")
        event.stop_event()

    @filter.command("解禁")
    async def cancel_ban(self, event: AiocqhttpMessageEvent):
        """解禁@user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("cancel_ban_perm")
        ):
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            await client.set_group_ban(
                group_id=int(group_id), user_id=int(tid), duration=0
            )
        event.stop_event()

    @filter.command("全体禁言")
    async def set_whole_ban(self, event: AiocqhttpMessageEvent):
        """全体禁言"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_whole_ban_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_whole_ban(group_id=int(group_id), enable=True)
        yield event.plain_result("已开启全体禁言")

    @filter.command("解除全体禁言")
    async def cancel_whole_ban(self, event: AiocqhttpMessageEvent):
        """解除全体禁言"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("cancel_whole_ban_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_whole_ban(group_id=int(group_id), enable=False)
        yield event.plain_result("已解除全体禁言")

    @filter.command("改名")
    async def set_card(
        self, event: AiocqhttpMessageEvent, target_card: str | None = None
    ):
        """改名 xxx @user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_card_perm")
        ):
            yield event.plain_result(result)
            return
        if not target_card:
            yield event.plain_result("你又不说改什么昵称")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            replay = f"已将{target_name}的群昵称改为【{target_card}】"
            yield event.plain_result(replay)
            await client.set_group_card(
                group_id=int(group_id), user_id=int(tid), card=target_card
            )

    @filter.command("改我")
    async def set_card_me(
        self, event: AiocqhttpMessageEvent, target_card: str | None = None
    ):
        """改我 xxx"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_card_me_perm")
        ):
            yield event.plain_result(result)
            return
        if not target_card:
            yield event.plain_result("你又不说要改成啥昵称")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        await client.set_group_card(
            group_id=int(group_id), user_id=int(send_id), card=target_card
        )
        yield event.plain_result(f"已将你的群昵称改为【{target_card}】")

    @filter.command("头衔")
    async def set_title(
        self, event: AiocqhttpMessageEvent, new_title: str | None = None
    ):
        """头衔 xxx @user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_title_perm"), bot_perm="群主"
        ):
            yield event.plain_result(result)
            return
        if not new_title:
            yield event.plain_result("你又不说给什么头衔")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            yield event.plain_result(f"已将{target_name}的头衔改为【{new_title}】")
            await client.set_group_special_title(
                group_id=int(group_id),
                user_id=int(tid),
                special_title=new_title,
                duration=-1,
            )

    @filter.command("我要头衔")
    async def set_title_me(
        self, event: AiocqhttpMessageEvent, new_title: str | None = None
    ):
        """我要头衔 xxx"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_title_me_perm"), bot_perm="群主"
        ):
            yield event.plain_result(result)
            return
        if not new_title:
            yield event.plain_result("你又不说要什么头衔")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        await client.set_group_special_title(
            group_id=int(group_id),
            user_id=int(send_id),
            special_title=new_title,
            duration=-1,
        )
        yield event.plain_result(f"已将你的头衔改为【{new_title}】")

    @filter.command("踢了")
    async def group_kick(self, event: AiocqhttpMessageEvent):
        """踢了@user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("group_kick_perm")
        ):
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result("你又不说踢了谁")
            return
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            await client.set_group_kick(
                group_id=int(group_id), user_id=int(tid), reject_add_request=False
            )
            yield event.plain_result(f"已将【{tid}-{target_name}】踢出本群")

    @filter.command("拉黑")
    async def group_block(self, event: AiocqhttpMessageEvent):
        """拉黑 @user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("group_block_perm")
        ):
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result("你又不说拉黑谁")
            return
        client = event.bot
        group_id = event.get_group_id()
        for tid in tids:
            target_name = await self.get_nickname(event, user_id=tid)
            await client.set_group_kick(
                group_id=int(group_id), user_id=int(tid), reject_add_request=True
            )
            yield event.plain_result(f"已将【{tid}-{target_name}】踢出本群并拉黑!")

    @filter.command("设置管理员")
    async def set_admin(self, event: AiocqhttpMessageEvent):
        """设置管理员@user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_admin_perm"), bot_perm="群主"
        ):
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result("想设置谁为管理员？")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_admin(
                group_id=int(group_id), user_id=int(tid), enable=True
            )
            chain = [Comp.At(qq=tid), Comp.Plain(text="你已被设置为管理员")]
            yield event.chain_result(chain)

    @filter.command("取消管理员")
    async def cancel_admin(self, event: AiocqhttpMessageEvent):
        """取消管理员@user"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("cancel_admin_perm"), bot_perm="群主"
        ):
            yield event.plain_result(result)
            return
        tids = self.get_ats(event)
        if not tids:
            yield event.plain_result("想取消谁的管理员身份？")
            return
        client = event.bot
        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        tids = self.get_ats(event) or [send_id]
        for tid in tids:
            await client.set_group_admin(
                group_id=int(group_id), user_id=int(tid), enable=False
            )
            chain = [Comp.At(qq=tid), Comp.Plain(text="你的管理员身份已被取消")]
            yield event.chain_result(chain)

    @filter.command("设精", alias={"设置群精华"})
    async def set_essence(self, event: AiocqhttpMessageEvent):
        """将引用消息添加到群精华"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_essence_perm")
        ):
            yield event.plain_result(result)
            return
        chain = event.get_messages()
        first_seg = chain[0]
        if isinstance(first_seg, Comp.Reply):
            client = event.bot
            reply_id = first_seg.id
            try:
                await client.set_essence_msg(message_id=int(reply_id))
                yield event.plain_result("设了")
            except:  # noqa: E722
                yield event.plain_result("我可设置不了群精华")

    @filter.command("取精", alias={"取消群精华"})
    async def cancel_essence(self, event: AiocqhttpMessageEvent):
        """将引用消息移出群精华"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("cancel_essence_perm")
        ):
            yield event.plain_result(result)
            return
        chain = event.get_messages()
        first_seg = chain[0]
        if isinstance(first_seg, Comp.Reply):
            client = event.bot
            reply_id = first_seg.id
            try:
                await client.delete_essence_msg(message_id=int(reply_id))
                yield event.plain_result("取消了")
            except:  # noqa: E722
                yield event.plain_result("我可取消不了群精华")

    @filter.command("群精华")
    async def get_essence_msg_list(self, event: AiocqhttpMessageEvent):
        """查看群精华"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("get_essence_msg_list_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        essence_data = await client.get_essence_msg_list(group_id=group_id)
        yield event.plain_result(f"{essence_data}")
        event.stop_event()
        # TODO 做张好看的图片来展示

    @filter.command("撤回")
    async def delete_msg(self, event: AiocqhttpMessageEvent):
        """撤回 引用的消息 和 发送的消息"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("delete_msg_perm"), bot_perm="成员"
        ):
            yield event.plain_result(result)
            return
        chain = event.get_messages()
        first_seg = chain[0]
        if isinstance(first_seg, Comp.Reply):
            client = event.bot
            try:
                reply_id = first_seg.id
                await client.delete_msg(message_id=int(reply_id))
                event.stop_event()
            except:  # noqa: E722
                yield event.plain_result("我可撤回不了这条消息")
            try:
                message_id = event.message_obj.message_id
                await client.delete_msg(message_id=int(message_id))
            except:  # noqa: E722
                event.stop_event()

    @filter.command("设置群头像")
    async def set_group_portrait(self, event: AiocqhttpMessageEvent):
        """(引用图片)设置群头像"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_group_portrait_perm")
        ):
            yield event.plain_result(result)
            return
        chain = event.get_messages()
        img_url = None
        for seg in chain:
            if isinstance(seg, Comp.Image):
                img_url = seg.url
                break
            elif isinstance(seg, Comp.Reply):
                if seg.chain:
                    for reply_seg in seg.chain:
                        if isinstance(reply_seg, Comp.Image):
                            img_url = reply_seg.url
                            break

        if not img_url:
            yield event.plain_result("需要引用一张图片")
            return

        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_portrait(group_id=group_id, file=img_url)
        yield event.plain_result("群头像更新啦>v<")

    @filter.command("设置群名")
    async def set_group_name(
        self, event: AiocqhttpMessageEvent, group_name: str | None = None
    ):
        """/设置群名 xxx"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("set_group_name_perm")
        ):
            yield event.plain_result(result)
            return
        if not group_name:
            yield event.plain_result("你又不说要改成什么群名")
            return

        client = event.bot
        group_id = event.get_group_id()
        await client.set_group_name(group_id=int(group_id), group_name=group_name)
        yield event.plain_result("群名更新啦>v<")

    @filter.command("群友信息")
    async def get_group_member_list(self, event: AiocqhttpMessageEvent):
        """查看群友信息，人数太多时可能会处理失败"""
        if result := await self.perm_block(
            event,
            user_perm=self.perms.get("get_group_member_list_perm"),
            bot_perm="成员",
        ):
            yield event.plain_result(result)
            return
        yield event.plain_result("获取中...")
        client = event.bot
        group_id = event.get_group_id()
        members_data = await client.get_group_member_list(group_id=int(group_id))
        info_list = [
            (
                f"{self.format_join_time(member['join_time'])}："
                f"【{member['level']}】"
                f"{member['user_id']}-"
                f"{member['nickname']}"
            )
            for member in members_data
        ]
        info_list.sort(key=lambda x: datetime.strptime(x.split("：")[0], "%Y-%m-%d"))
        info_str = "进群时间：【等级】QQ-昵称\n\n"
        info_str += "\n\n".join(info_list)
        # TODO 做张好看的图片来展示
        url = await self.text_to_image(info_str)
        yield event.image_result(url)

    @filter.command("发布群公告")
    async def send_group_notice(
        self, event: AiocqhttpMessageEvent, content: str | None = None
    ):
        """(可引用一张图片)/发布群公告 xxx"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("send_group_notice_perm")
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        image_url = ""
        save_path = ""
        chain = event.get_messages()
        for seg in chain:
            if isinstance(seg, Comp.Image):
                image_url = seg.url
                break
            elif isinstance(seg, Comp.Reply):
                if seg.chain:
                    for reply_seg in seg.chain:
                        if isinstance(reply_seg, Comp.Image):
                            image_url = reply_seg.url
                            break
        if image_url:
            image_bytes = await self.download_image(image_url)
            if not image_bytes:
                yield event.plain_result("图片获取失败")
                return

            index = len(list(TEMP_DIR.rglob("*.jpg")))
            save_path = str(TEMP_DIR / f"{index}.jpg")
            with open(save_path, "wb") as f:
                f.write(image_bytes)

        await client._send_group_notice(
            group_id=group_id, content=content, image=save_path
        )

    @filter.command("群公告")
    async def get_group_notice(self, event: AiocqhttpMessageEvent):
        """查看群公告"""
        if result := await self.perm_block(
            event, user_perm=self.perms.get("get_group_notice_perm"), bot_perm="成员"
        ):
            yield event.plain_result(result)
            return
        client = event.bot
        group_id = event.get_group_id()
        notices = await client._get_group_notice(group_id=group_id)

        formatted_messages = []
        for notice in notices:
            sender_id = notice["sender_id"]
            publish_time = datetime.fromtimestamp(notice["publish_time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            message_text = notice["message"]["text"].replace("&#10;", "\n\n")

            formatted_message = (
                f"【{publish_time}-{sender_id}】\n\n"
                f"{textwrap.indent(message_text, '    ')}"
            )
            formatted_messages.append(formatted_message)

        notices_str = "\n\n\n".join(formatted_messages)
        url = await self.text_to_image(notices_str)
        yield event.image_result(url)
        # TODO 做张好看的图片来展示

    @staticmethod
    def format_join_time(timestamp):
        """格式化时间戳"""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    @staticmethod
    async def download_image(url: str) -> bytes | None:
        """下载图片"""
        url = url.replace("https://", "http://")
        try:
            async with aiohttp.ClientSession() as client:
                response = await client.get(url)
                img_bytes = await response.read()
                return img_bytes
        except Exception as e:
            logger.error(f"图片下载失败: {e}")

    @filter.command("设置宵禁")
    async def scheduler_loop(
        self,
        event: AiocqhttpMessageEvent,
        input_start_time: str | None = None,
        input_end_time: str | None = None,
    ):
        """后台调度器，每 10 秒检查一次宵禁任务条件, 条件满足则执行"""
        client = event.bot
        group_id = event.get_group_id()
        # 没有传入时间参数时，使用默认的宵禁时间
        start_time = input_start_time or self.night_start_time
        end_time = input_end_time or self.night_end_time
        # 去除空格等，替换中文冒号为英文冒号
        start_time = start_time.strip().replace("：", ":")
        end_time = end_time.strip().replace("：", ":")
        # 转化为时间对象
        target_start_time = datetime.strptime(start_time, "%H:%M").time()
        target_end_time = datetime.strptime(end_time, "%H:%M").time()
        await client.send_group_msg(
            group_id=int(group_id),
            message=f"已创建宵禁任务：{start_time}~{end_time}",
        )
        whole_ban_status = False # 全体禁言状态
        # 进入循环，检查时间
        while True:
            await asyncio.sleep(10)
            current_time = datetime.now().time()
            if target_start_time <= current_time <= target_end_time:
                if whole_ban_status is False:
                    try:
                        await client.send_group_msg(
                            group_id=int(group_id),
                            message="宵禁开启时间到！",
                        )
                        await client.set_group_whole_ban(
                            group_id=int(group_id), enable=True
                        )
                        whole_ban_status = True
                    except Exception as e:
                        logger.error(f"开启宵禁失败: {e}")
                        continue

            else:
                if whole_ban_status is True:
                    try:
                        await client.send_group_msg(
                            group_id=int(group_id),
                            message="宵禁结束时间到！",
                        )
                        await client.set_group_whole_ban(
                            group_id=int(group_id), enable=False
                        )
                        whole_ban_status = False
                    except Exception as e:
                        logger.error(f"解除宵禁失败: {e}")
                        continue

    @filter.command("取消宵禁")
    async def cancel_scheduler_loop(self, event: AiocqhttpMessageEvent):
        """取消宵禁"""

