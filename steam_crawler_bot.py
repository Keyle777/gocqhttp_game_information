import base64
import io
import json
import os
import re
from aiocqhttp import CQHttp, ApiError, Event
from bs4 import BeautifulSoup as bs
from PIL import Image, ImageDraw, ImageFont
import math
from ast import Return
from datetime import datetime
import traceback
import requests
import asyncio

import urllib.request
from urllib.parse import quote
import string
from xml.dom import minidom



# 配置项
# 代理ip设置
proxies = {}

header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, br",
}
# 图片形式的消息里最多展现的项目数量
Limit_num = 20

# 促销提醒的图片的数据来源，1为steam，0为小黑盒，当数据来源获取失败时会切换另一个来源
sell_remind_data_from_steam = 0

# 与steam和小黑盒有关的消息是否以图片形式发送，默认为否，注意，如果消息被风控发不出去，会自动转为图片发送
send_pic_mes = False

# 其他必需的配置项，不了解的话请勿乱改
s = requests.session()
FILE_PATH = os.path.dirname(__file__)
url_new = "https://store.steampowered.com/search/results/?l=schinese&query&sort_by=Released_DESC&category1=998&os=win&start=0&count=50"
url_specials = "https://store.steampowered.com/search/results/?l=schinese&query&sort_by=_ASC&category1=998&specials=1&os=win&filter=topsellers&start=0&count=50"
group_id = xxx # 群号
bot_id = xxx # 机器人QQ号
def other_request(url, headers=None, cookie=None):
    try:
        content = s.get(url, headers=headers, cookies=cookie, timeout=4)
    except Exception:
        content = s.get(url, headers=headers, cookies=cookie, proxies=proxies, timeout=4)
    return content


bot = CQHttp(
    api_root='http://127.0.0.1:5700/',  # 如果使用反向 WebSocket，这里不需要传入
)

def get_weather_by_city(city_name):
    def get_weather(name):
        page = urllib.request.urlopen("http://www.webxml.com.cn/WebServices/WeatherWebService.asmx/getWeatherbyCityName?theCityName=" + name)
        lines = page.readlines()
        page.close()
        document = ""
        for line in lines:
            document = document + line.decode('utf-8')

        from xml.dom.minidom import parseString
        dom = parseString(document)
        strings = dom.getElementsByTagName("string")
        return strings[10].childNodes[0].data

    city_name_encoded = quote(city_name, safe=string.printable)
    city_weather = get_weather(city_name_encoded)
    if city_weather:
        return city_weather
    else:
        return '未找到该城市的天气信息'


head = {
    "User-Agent": "Mozilla/5.0 (Linux; U; Android 8.1.0; zh-cn; BLA-AL00 Build/HUAWEIBLA-AL00) AppleWebKit/537.36 \
    (KHTML, like Gecko) Version/4.0 Chrome/57.0.2987.132 MQQBrowser/8.9 Mobile Safari/537.36"
}


def xjy_compare():
    """
    爬取it之家喜加一页面数据,对比data文件夹中xjy_result.json已记录的数据及新数据
    返回一个对比列表,列表里包含了新更新的文章链接
    """
    data = {}
    xjy_url = "https://www.ithome.com/tag/xijiayi"
    try:
        xjy_page = other_request(url=xjy_url, headers=head).text
        soup = bs(xjy_page, "lxml")
        url_new = []
        for xjy_info in soup.find_all(name="a", class_="title"):
            info_soup = bs(str(xjy_info), "lxml")
            url_new.append(info_soup.a["href"])
        if url_new == []:
            return "Server Error"
        else:
            if not os.path.exists(os.path.join(FILE_PATH, "data/xjy_result.json")):
                with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "w+", encoding="utf-8") as f:
                    data["url"] = url_new
                    data["groupid"] = []
                    f.write(json.dumps(data, ensure_ascii=False))
            url_old = []
            with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "r+", encoding="utf-8") as f:
                content = json.loads(f.read())
                url_old = content["url"]
                groupid = content["groupid"]
            seta = set(url_new)
            setb = set(url_old)
            compare_list = list(seta - setb)
            with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "w+", encoding="utf-8") as f:
                data["url"] = url_new
                data["groupid"] = groupid
                f.write(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        compare_list = f"xjy_compare_error:{e}"

    return compare_list


def xjy_result(model, compare_list):
    """
    model为Default时则compare_list为xjy_compare返回的对比列表
    model为Query时则compare_list为要查询的项目数量,从data文件夹中xjy_result.json取得对应数量的链接列表
    按照一定格式处理从文章链接爬取的数据并返回
    """
    result_text_list = []
    xjy_list = []
    if model == "Default":
        xjy_list = compare_list
    elif model == "Query":
        with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "r+", encoding="utf-8") as f:
            url = json.loads(f.read())["url"]
            for i in url:
                xjy_list.append(i.strip())
                if url.index(i) == compare_list - 1:
                    break
    try:
        for news_url in xjy_list:
            page = other_request(url=news_url, headers=head).text
            soup = bs(page, "lxml")
            info_soup = bs(str(soup.find(name="div", class_="post_content")), "lxml").find_all(name="p")
            second_text = ""
            for i in info_soup:
                if i.a != None:
                    if i.a["href"] == "https://www.ithome.com/":
                        text = i.text + "|"
                    elif "ithome" in i.a["href"]:
                        text = ""
                    elif "ithome_super_player" in i.a.get("class", ""):
                        text = i.text + "|"
                    else:
                        text = i.a["href"] + "|"
                    first_text = text
                else:
                    first_text = i.text + "|"
                second_text += first_text.replace("\xa0", " ")
            temp_text = second_text.split("|")
            third_text = list(set(temp_text))
            third_text.sort(key=temp_text.index)
            xjy_url_text = ""
            for part in third_text:
                if "http" in part:
                    xjy_url_text += "领取地址:" + part + "\n"
            full_text = ""
            for i in third_text:
                if "https://" in i or "http://" in i:
                    continue
                full_text += i
            final_text = f"{third_text[0]}......(更多内容请阅读原文)\n{xjy_url_text}"
            result_text_list.append(final_text + f"原文地址:{news_url}")
    except Exception as e:
        full_text = ""
        result_text_list = f"xjy_result_error:{e}"

    return result_text_list, full_text


def xjy_remind_group(groupid, add: bool):
    with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "r") as f:
        data = json.loads(f.read())
    groupid_list = data["groupid"]
    if add:
        groupid_list.append(groupid)
        data["groupid"] = groupid_list
    if not add:
        data["groupid"].remove(groupid)
    with open(os.path.join(FILE_PATH, "data/xjy_result.json"), "w") as f:
        f.write(json.dumps(data, ensure_ascii=False))

# 文本转图像
def text_to_img(text):
    font_path = os.path.join(FILE_PATH, "msyh.ttc")
    font = ImageFont.truetype(font_path, 16)
    a = re.findall(r".{1,30}", text.replace(" ", ""))
    text = "\n".join(a)
    width, height = font.getsize_multiline(text.strip())
    img = Image.new("RGB", (width + 20, height + 20), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, font=font, fill=(0, 0, 0))
    b_io = io.BytesIO()
    img.save(b_io, format="JPEG")
    base64_str = "base64://" + base64.b64encode(b_io.getvalue()).decode()
    return base64_str


xjy_compare()

with open(os.path.join(FILE_PATH, "data/tag.json"), "r", encoding="utf-8") as f:
    tagdata = json.loads(f.read())
# steam爬虫
def steam_crawler(url_choose: str):
    result = []
    get_url = other_request(url_choose).text
    soup = bs(get_url.replace(r"\n", "").replace(r"\t", "").replace(r"\r", "").replace("\\", ""), "lxml")
    row_list = soup.find_all(name="a", class_="search_result_row")
    for row in row_list:
        appid = row.get("data-ds-appid")
        gameinfo = {
            "标题": row.find(name="span", class_="title").text,
            "链接": row.get("href"),
            "appid": appid,
            "高分辨率图片": f"https://media.st.dl.pinyuncloud.com/steam/apps/{appid}/capsule_231x87.jpg",
            "低分辨率图片": row.find(name="img").get("src"),
        }
        if not row.find(name="div", class_="discount_pct"):
            try:
                price = (
                    row.find(name="div", class_="discount_final_price")
                    .text.replace("\r", "")
                    .replace("\n", "")
                    .replace(" ", "")
                )
                gameinfo["折扣价"] = " "
                if price != "" and "免费" not in price and "Free" not in price:
                    gameinfo["原价"] = price
                elif "免费" in price or "Free" in price:
                    gameinfo["原价"] = "免费开玩"
                else:
                    gameinfo["原价"] = "无价格信息"
            except Exception:
                gameinfo["原价"] = "无价格信息"
                gameinfo["折扣价"] = " "
        else:
            discount_price = row.find(name="div", class_="discount_final_price").text.strip().replace(" ", "")
            discount_percent = row.find(name="div", class_="discount_pct").text.replace("\n", "").strip()
            gameinfo["原价"] = row.find(name="div", class_="discount_original_price").text.strip().replace(" ", "")
            gameinfo["折扣价"] = f'{str(discount_price).strip().replace(" ", "")}({discount_percent})'
        try:
            rate = row.find(name="span", class_="search_review_summary").get("data-tooltip-html")
            gameinfo["评测"] = rate.replace("<br>", ",").replace(" ", "")
        except Exception:
            gameinfo["评测"] = "暂无评测"
        try:
            tag = row.get("data-ds-tagids").strip("[]").split(",")
            tagk = "".join(tagdata["tag_dict"].get(i) + "," for i in tag)
            gameinfo["标签"] = tagk.strip(",")
        except Exception:
            gameinfo["标签"] = "无用户标签"
        result.append(gameinfo)

    return result


# 根据传入的tag创建tag搜索链接，返回tag搜索链接以及传入的tag中有效的tag(有效tag具体参考data文件夹中的tag.json)
def tagurl_creater(tag: list, page: int):
    tag_search_num = "&tags="
    tag_name = ""
    tag_list = tag
    count = f"&start={(page-1)*50}&count=50"
    for i in tag_list:
        if tagdata["tag_dict"].get(i, "") != "":
            tag_search_num += tagdata["tag_dict"][i] + ","
            tag_name += f"{i},"
    tag_search_url = (
        "https://store.steampowered.com/search/results/?l=schinese&query&force_infinite=1&filter=topsellers&category1=998&infinite=1"
        + tag_search_num.strip(",")
        + count
    )
    return tag_search_url, tag_name.strip(",")


def mes_creater(result: dict):
    mes_list = []
    for i in range(len(result)):
        if result[i]["原价"] in ["免费开玩", "无价格信息"]:
            mes = f"[CQ:image,file={result[i]['低分辨率图片']}]\n{result[i]['标题']}\n原价:{result[i]['原价']}\
                \n链接:{result[i]['链接']}\n{result[i]['评测']}\n用户标签:{result[i]['标签']}\nappid:{result[i]['appid']}"
        else:
            mes = f"[CQ:image,file={result[i]['低分辨率图片']}]\n{result[i]['标题']}\n原价:{result[i]['原价']} 折扣价:{result[i]['折扣价']}\
                \n链接:{result[i]['链接']}\n{result[i]['评测']}\n用户标签:{result[i]['标签']}\nappid:{result[i]['appid']}"
        data = {"type": "node", "data": {"name": "可可机器人", "uin": "2272628106", "content": mes}}
        mes_list.append(data)
    return mes_list



font_path = os.path.join(FILE_PATH, "msyh.ttc")
font1 = ImageFont.truetype(font_path, 18)
font2 = ImageFont.truetype(font_path, 12)
font3 = ImageFont.truetype(font_path, 13)


def resize_font(font_size, text_str, limit_width):
    """
    在给定的长度内根据文字内容来改变文字的字体大小
    font_size为默认大小,即如果函数判断以此字体大小所绘制出来的文字内容不会超过给定的长度时,则保持这个大小
    若绘制出来的文字内容长度大于给定长度,则会不断对减小字体大小直至刚好小于给定长度
    text_str为文字内容,limit_width为给定的长度
    返回内容为PIL.ImageFont.FreeTypeFont对象,以及调整字体过后的文字长宽
    """

    font = ImageFont.truetype(font_path, font_size)
    font_lenth = font.getsize(str(text_str))[0]
    while font_lenth > limit_width:
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)
        font_lenth = font.getsize(str(text_str))[0]
    font_width = font.getsize(str(text_str))[1]

    return font, font_lenth, font_width


def steam_monitor():
    url = "https://keylol.com"
    r = other_request(url).text
    soup = bs(r, "lxml")
    stat = soup.find(name="div", id="steam_monitor")
    a = stat.findAll(name="a")
    for i in a:
        if "状态" in str(i.text):
            continue
        sell_name = i.text.replace(" ", "").strip()
    script = stat.find_next_sibling(name="script").string
    date = re.findall(r'new Date\("(.*?)"', script)[0]
    if date == "":
        sell_date = "促销已经结束"
        return sell_name, sell_date
    a = datetime.strptime(date, "%Y-%m-%d %H:%M")
    b = datetime.now()
    xc = (a - b).total_seconds()
    m, s = divmod(int(xc), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    sell_date = "%d日%d时%d分%d秒" % (d, h, m, s)
    return sell_name, sell_date


def pic_creater(data: list, num=Limit_num, is_steam=True, monitor_on=False):
    """
    生成一个图片,data为小黑盒或steam爬取的数据 num为图片中游戏项目的数量,默认为config.py里设定的数量
    is_steam为判断传入的数据是否steam来源,monitor_on为是否加入促销活动信息 两者需手动指定
    """
    if len(data) < num:
        num = len(data)

    if monitor_on:
        background = Image.new("RGB", (520, (60 + 10) * num + 10 + 110), (27, 40, 56))
        start_pos = 110
        sell_info = steam_monitor()
        sell_bar = Image.new("RGB", (500, 100), (22, 32, 45))
        draw_sell_bar = ImageDraw.Draw(sell_bar, "RGB")
        uppper_text = sell_info[0].split(":")[0]
        if "正在进行中" in sell_info[0].split(":")[1]:
            lower_text = f"正在进行中(预计{sell_info[1]}后结束)"
            cdtext_color = (255, 0, 0)
        elif "结束" in sell_info[1]:
            lower_text = f"{sell_info[1]}"
            cdtext_color = (109, 115, 126)
        else:
            lower_text = f"预计{sell_info[1]}后开始"
            cdtext_color = (0, 255, 0)
        uppper_text_font = resize_font(20, uppper_text, 490)
        draw_sell_bar.text(
            ((500 - uppper_text_font[1]) / 2, 20), uppper_text, font=uppper_text_font[0], fill=(199, 213, 224)
        )
        draw_sell_bar.text(((500 - font1.getsize(lower_text)[0]) / 2, 62), lower_text, font=font1, fill=cdtext_color)
        background.paste(sell_bar, (10, 10))
    else:
        background = Image.new("RGB", (520, (60 + 10) * num + 10), (27, 40, 56))
        start_pos = 0

    for i in range(num):
        game_bgbar = Image.new("RGB", (500, 60), (22, 32, 45))
        draw_game_bgbar = ImageDraw.Draw(game_bgbar, "RGB")

        if not is_steam:
            if "非steam平台" in data[i].get("平台", ""):
                a = other_request(data[i].get("其他平台图片"), headers=header).content
                aimg_bytestream = io.BytesIO(a)
                a_imgb = Image.open(aimg_bytestream).resize((160, 60))
                game_bgbar.paste(a_imgb, (0, 0))
                draw_game_bgbar.text((165, 5), data[i].get("标题"), font=font1, fill=(199, 213, 224))
                draw_game_bgbar.text((165, 35), data[i].get("平台"), font=font2, fill=(199, 213, 224))
                background.paste(game_bgbar, (10, 60 * i + 10 * (i + 1)))
                continue

        try:
            if not is_steam:
                a = other_request(data[i].get("图片"), headers=header).content
            else:
                a = other_request(data[i].get("高分辨率图片")).content
            aimg_bytestream = io.BytesIO(a)
            a_imgb = Image.open(aimg_bytestream).resize((160, 60))
        except:
            a = other_request(data[i].get("低分辨率图片")).content
            aimg_bytestream = io.BytesIO(a)
            a_imgb = Image.open(aimg_bytestream).resize((160, 60))
        game_bgbar.paste(a_imgb, (0, 0))

        if is_steam:
            rate_bg = Image.new("RGBA", (54, 18), (0, 0, 0, 200))
            a = rate_bg.split()[3]
            game_bgbar.paste(rate_bg, (106, 0), a)
            draw_game_bgbar.text((107, 0), data[i].get("评测").split(",")[0], font=font3, fill=(255, 255, 225))

        gameinfo_area = Image.new("RGB", (280, 60), (22, 32, 45))
        draw_gameinfo_area = ImageDraw.Draw(gameinfo_area, "RGB")
        draw_gameinfo_area.text((0, 5), data[i].get("标题"), font=font1, fill=(199, 213, 224))
        if is_steam:
            draw_gameinfo_area.text((0, 35), data[i].get("标签"), font=font2, fill=(199, 213, 224))
        else:
            if data[i].get("原价") == "免费开玩":
                text = "免费开玩"
            elif "获取失败" in data[i].get("原价"):
                text = "获取失败!可能为免费游戏"
            elif data[i].get("平史低价") == "无平史低价格信息":
                text = "无平史低价格信息"
            elif data[i].get("折扣比") == "当前无打折信息":
                text = f"平史低价:¥{data[i].get('平史低价')} | 当前无打折信息"
            else:
                text = f"平史低价:¥{data[i].get('平史低价')} | {data[i].get('是否史低')} | {data[i].get('截止日期')} | {data[i].get('是否新史低') if data[i].get('是否新史低')!=' ' else '不是新史低'}"
            draw_gameinfo_area.text((0, 35), text, font=font2, fill=(199, 213, 224))
        game_bgbar.paste(gameinfo_area, (165, 0))

        if (is_steam and data[i].get("折扣价", " ") != " ") or (
            not is_steam and "免费" not in data[i].get("原价") and data[i].get("折扣比") != "当前无打折信息"
        ):
            if is_steam:
                original_price = data[i].get("原价")
                discount_price, discount_percent = re.findall(r"^(.*?)\((.*?)\)", data[i].get("折扣价"))[0]
            else:
                original_price = f"¥{data[i].get('原价')}"
                discount_price = f"¥{data[i].get('当前价')}"
                discount_percent = f"-{data[i].get('折扣比')}%"
            green_bar = Image.new(
                "RGB", (font2.getsize(discount_percent)[0], font2.getsize(discount_percent)[1] + 4), (76, 107, 34)
            )
            game_bgbar.paste(green_bar, (math.ceil(445 + (55 - font2.getsize(discount_percent)[0]) / 2), 4))
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(discount_percent)[0]) / 2), 4),
                discount_percent,
                font=font2,
                fill=(199, 213, 224),
            )
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(original_price)[0]) / 2), 22),
                original_price,
                font=font2,
                fill=(136, 136, 136),
            )
            del_line = Image.new("RGB", (font2.getsize(original_price)[0], 1), (136, 136, 136))
            game_bgbar.paste(
                del_line,
                (
                    445 + math.ceil((55 - font2.getsize(original_price)[0]) / 2),
                    22 + math.ceil(font2.getsize(original_price)[1] / 2) + 2,
                ),
            )
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(discount_price)[0]) / 2), 40),
                discount_price,
                font=font2,
                fill=(199, 213, 224),
            )
        else:
            if is_steam:
                original_price = data[i].get("原价")
            elif data[i].get("原价") == "免费开玩":
                original_price = "免费开玩"
            elif "获取失败" in data[i].get("原价"):
                original_price = "获取失败"
            else:
                original_price = "¥" + data[i].get("原价")
            temp_font = resize_font(12, original_price, 55)
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - temp_font[1]) / 2), math.ceil(30 - temp_font[2] / 2)),
                original_price,
                font=temp_font[0],
                fill=(199, 213, 224),
            )

        background.paste(game_bgbar, (10, start_pos + 60 * i + 10 * (i + 1)))

    b_io = io.BytesIO()
    background.save(b_io, format="JPEG")
    base64_str = "base64://" + base64.b64encode(b_io.getvalue()).decode()
    return base64_str


def sell_remind_group(groupid, add: bool):
    data = {}
    if not os.path.exists(os.path.join(FILE_PATH, "data/sell_remind_group.txt")):
        with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "w", encoding="utf-8") as f:
            data["groupid"] = []
            f.write(json.dumps(data, ensure_ascii=False))
    with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "r", encoding="utf-8") as f:
        data = json.loads(f.read())
    groupid_list = data["groupid"]
    if add:
        groupid_list.append(groupid)
        data["groupid"] = groupid_list
    if not add:
        data["groupid"].remove(groupid)
    with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False))



# 匹配关键词发送相关信息,例:今日特惠,发送今日特惠信息,今日新品则发送新品信息
@bot.on_message()
async def Gameinfo(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106]" in event.raw_message:
        trimmed_message = event.message[event.message.index(']') + 1:].strip()
        model = trimmed_message.strip()
        try:
            if model == "今日新品":
                data = steam_crawler(url_new)
            elif model == "今日特惠":
                data = steam_crawler(url_specials)
            else:
                return
        except Exception as e:
            print(f"哦吼,出错了,报错内容为:{e},请检查运行日志!" + f"Error:{traceback.format_exc()}")
            await bot.api.send_group_msg(group_id=group_id, message=data, auto_escape=False, self_id=bot_id)
            return
        try:
            if send_pic_mes:
                await bot.api.send_group_msg(group_id=group_id, message=f"[CQ:image,file={pic_creater(data, is_steam=True)}]", auto_escape=False, self_id=bot_id)
                return
            await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater(data))
        except Exception as err:
            if "retcode=100" in str(err):
                if send_pic_mes:
                    await bot.api.send_group_forward_msg(group_id=group_id, message=mes_creater(data))
                    return
                await bot.api.send_group_msg(group_id=group_id, message=f"[CQ:image,file={pic_creater(data, is_steam=True)}]", auto_escape=False, self_id=bot_id)
            else:
                print(f"Error:{traceback.format_exc()}")
                await bot.api.send_group_msg(group_id=group_id, message=f"发生了其他错误,报错内容为{err},请检查运行日志!", auto_escape=True, self_id=bot_id)


# 后接格式:页数(阿拉伯数字) 标签1 标签2,例:st搜标签 动作 射击
@bot.on_message()
async def search_tag(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] st搜" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        try:
            if mes.startswith("st搜标签"):
                tags = mes[5:].split(" ")
                tagurl = tagurl_creater(tags, 1)
                print(tagurl)
                if tagurl[1] == "":
                    await bot.api.send_group_msg(group_id=group_id, message="没有匹配到有效标签", auto_escape=False, self_id=bot_id)
                    return
                data = steam_crawler(tagurl[0])
            elif mes.startswith("st搜游戏"):
                gamename = mes[5:].split(" ")
                tagurl = tagurl_creater(gamename, 1)
                if gamename == "":
                    await bot.api.send_group_msg(group_id=group_id, message="没有匹配到有效游戏", auto_escape=False, self_id=bot_id)
                    return
                search_url = f"https://store.steampowered.com/search/results/?l=schinese&query&start=0&count=20&dynamic_data=&sort_by=_ASC&snr=1_7_7_151_7&infinite=1&term={gamename}"
                data = steam_crawler(search_url)
                if len(data) == 0:
                    await bot.api.send_group_msg(group_id=group_id, message="无搜索结果", auto_escape=False, self_id=bot_id)
                    return
        except Exception as e:
            print(f"Error:{traceback.format_exc()}")
            await bot.api.send_group_msg(group_id=group_id, message=f"哦吼,出错了,报错内容为{e},请检查运行日志!", auto_escape=False, self_id=bot_id)
            return
        try:
            if send_pic_mes:
                await bot.api.send_group_msg(group_id=group_id, message=f"[CQ:image,file={pic_creater(data, is_steam=True)}]", auto_escape=False, self_id=bot_id)
                return
            await bot.api.send_group_forward_msg(group_id=group_id, message=mes_creater(data))
        except Exception as err:
            if "retcode=100" in str(err):
                if send_pic_mes:
                    await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater(data))
                    return
                await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater(data))

@bot.on_message()
async def help(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] 帮助" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        if mes.startswith("帮助"):
            helpimg = Image.open(os.path.join(FILE_PATH, "data/help.png"))
            b_io = io.BytesIO()
            helpimg.save(b_io, format="png")
            base64_str = f"base64://{base64.b64encode(b_io.getvalue()).decode()}"
            await bot.send(event, message=f"[CQ:image,file={base64_str}]")

@bot.on_message()
async def WeatherData(event: Event):
    trimmed_message = event.message[event.message.index(']') + 1:].strip()
    mes = trimmed_message.strip()
    city_name = mes[:2]
    if event.message_type == 'group' and f"[CQ:at,qq=2272628106] {city_name}天气" in event.raw_message or f"@东西南北 {city_name}天气" in event.raw_message:
        if city_name:
            city_name = city_name[0]
        weather_data = get_weather_by_city(city_name)
        await bot.api.send_group_msg(group_id=group_id, message=weather_data, auto_escape=False, self_id=event.self_id)

# 后接想要的资讯条数（阿拉伯数字）
@bot.on_message()
async def xjy_info(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] 喜加一" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        if not os.path.exists(os.path.join(FILE_PATH, "data/xjy_result.json")):
            try:
                xjy_compare()
            except Exception as e:
                print(f"Error:{traceback.format_exc()}")
        if mes.startswith("喜加一资讯"):
            num = mes[5:].split(" ")
            result = xjy_result("Query", int(num[0]))[0]
            mes_list = []
            if "error" in result:
                print(result)
                return
            else:
                if len(result) <= 3:
                    for i in result:
                        await bot.api.send(event, message=i)
                else:
                    for i in result:
                        data = {"type": "node", "data": {"name": "可可机器人", "uin": "2272628106", "content": i}}
                        mes_list.append(data)
                    await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_list)


def steam_monitor():
    url = "https://keylol.com"
    r = other_request(url).text
    soup = bs(r, "lxml")
    stat = soup.find(name="div", id="steam_monitor")
    a = stat.findAll(name="a")
    for i in a:
        if "状态" in str(i.text):
            continue
        sell_name = i.text.replace(" ", "").strip()
    script = stat.find_next_sibling(name="script").string
    date = re.findall(r'new Date\("(.*?)"', script)[0]
    if date == "":
        sell_date = "促销已经结束"
        return sell_name, sell_date
    a = datetime.strptime(date, "%Y-%m-%d %H:%M")
    b = datetime.now()
    xc = (a - b).total_seconds()
    m, s = divmod(int(xc), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    sell_date = "%d日%d时%d分%d秒" % (d, h, m, s)
    return sell_name, sell_date


def pic_creater(data: list, num=Limit_num, is_steam=True, monitor_on=False):
    """
    生成一个图片,data为小黑盒或steam爬取的数据 num为图片中游戏项目的数量,默认为config.py里设定的数量
    is_steam为判断传入的数据是否steam来源,monitor_on为是否加入促销活动信息 两者需手动指定
    """
    if len(data) < num:
        num = len(data)

    if monitor_on:
        background = Image.new("RGB", (520, (60 + 10) * num + 10 + 110), (27, 40, 56))
        start_pos = 110
        sell_info = steam_monitor()
        sell_bar = Image.new("RGB", (500, 100), (22, 32, 45))
        draw_sell_bar = ImageDraw.Draw(sell_bar, "RGB")
        uppper_text = sell_info[0].split(":")[0]
        if "正在进行中" in sell_info[0].split(":")[1]:
            lower_text = f"正在进行中(预计{sell_info[1]}后结束)"
            cdtext_color = (255, 0, 0)
        elif "结束" in sell_info[1]:
            lower_text = f"{sell_info[1]}"
            cdtext_color = (109, 115, 126)
        else:
            lower_text = f"预计{sell_info[1]}后开始"
            cdtext_color = (0, 255, 0)
        uppper_text_font = resize_font(20, uppper_text, 490)
        draw_sell_bar.text(
            ((500 - uppper_text_font[1]) / 2, 20), uppper_text, font=uppper_text_font[0], fill=(199, 213, 224)
        )
        draw_sell_bar.text(((500 - font1.getsize(lower_text)[0]) / 2, 62), lower_text, font=font1, fill=cdtext_color)
        background.paste(sell_bar, (10, 10))
    else:
        background = Image.new("RGB", (520, (60 + 10) * num + 10), (27, 40, 56))
        start_pos = 0

    for i in range(num):
        game_bgbar = Image.new("RGB", (500, 60), (22, 32, 45))
        draw_game_bgbar = ImageDraw.Draw(game_bgbar, "RGB")

        if not is_steam:
            if "非steam平台" in data[i].get("平台", ""):
                a = other_request(data[i].get("其他平台图片"), headers=header).content
                aimg_bytestream = io.BytesIO(a)
                a_imgb = Image.open(aimg_bytestream).resize((160, 60))
                game_bgbar.paste(a_imgb, (0, 0))
                draw_game_bgbar.text((165, 5), data[i].get("标题"), font=font1, fill=(199, 213, 224))
                draw_game_bgbar.text((165, 35), data[i].get("平台"), font=font2, fill=(199, 213, 224))
                background.paste(game_bgbar, (10, 60 * i + 10 * (i + 1)))
                continue

        try:
            if not is_steam:
                a = other_request(data[i].get("图片"), headers=header).content
            else:
                a = other_request(data[i].get("高分辨率图片")).content
            aimg_bytestream = io.BytesIO(a)
            a_imgb = Image.open(aimg_bytestream).resize((160, 60))
        except:
            a = other_request(data[i].get("低分辨率图片")).content
            aimg_bytestream = io.BytesIO(a)
            a_imgb = Image.open(aimg_bytestream).resize((160, 60))
        game_bgbar.paste(a_imgb, (0, 0))

        if is_steam:
            rate_bg = Image.new("RGBA", (54, 18), (0, 0, 0, 200))
            a = rate_bg.split()[3]
            game_bgbar.paste(rate_bg, (106, 0), a)
            draw_game_bgbar.text((107, 0), data[i].get("评测").split(",")[0], font=font3, fill=(255, 255, 225))

        gameinfo_area = Image.new("RGB", (280, 60), (22, 32, 45))
        draw_gameinfo_area = ImageDraw.Draw(gameinfo_area, "RGB")
        draw_gameinfo_area.text((0, 5), data[i].get("标题"), font=font1, fill=(199, 213, 224))
        if is_steam:
            draw_gameinfo_area.text((0, 35), data[i].get("标签"), font=font2, fill=(199, 213, 224))
        else:
            if data[i].get("原价") == "免费开玩":
                text = "免费开玩"
            elif "获取失败" in data[i].get("原价"):
                text = "获取失败!可能为免费游戏"
            elif data[i].get("平史低价") == "无平史低价格信息":
                text = "无平史低价格信息"
            elif data[i].get("折扣比") == "当前无打折信息":
                text = f"平史低价:¥{data[i].get('平史低价')} | 当前无打折信息"
            else:
                text = f"平史低价:¥{data[i].get('平史低价')} | {data[i].get('是否史低')} | {data[i].get('截止日期')} | {data[i].get('是否新史低') if data[i].get('是否新史低')!=' ' else '不是新史低'}"
            draw_gameinfo_area.text((0, 35), text, font=font2, fill=(199, 213, 224))
        game_bgbar.paste(gameinfo_area, (165, 0))

        if (is_steam and data[i].get("折扣价", " ") != " ") or (
            not is_steam and "免费" not in data[i].get("原价") and data[i].get("折扣比") != "当前无打折信息"
        ):
            if is_steam:
                original_price = data[i].get("原价")
                discount_price, discount_percent = re.findall(r"^(.*?)\((.*?)\)", data[i].get("折扣价"))[0]
            else:
                original_price = f"¥{data[i].get('原价')}"
                discount_price = f"¥{data[i].get('当前价')}"
                discount_percent = f"-{data[i].get('折扣比')}%"
            green_bar = Image.new(
                "RGB", (font2.getsize(discount_percent)[0], font2.getsize(discount_percent)[1] + 4), (76, 107, 34)
            )
            game_bgbar.paste(green_bar, (math.ceil(445 + (55 - font2.getsize(discount_percent)[0]) / 2), 4))
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(discount_percent)[0]) / 2), 4),
                discount_percent,
                font=font2,
                fill=(199, 213, 224),
            )
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(original_price)[0]) / 2), 22),
                original_price,
                font=font2,
                fill=(136, 136, 136),
            )
            del_line = Image.new("RGB", (font2.getsize(original_price)[0], 1), (136, 136, 136))
            game_bgbar.paste(
                del_line,
                (
                    445 + math.ceil((55 - font2.getsize(original_price)[0]) / 2),
                    22 + math.ceil(font2.getsize(original_price)[1] / 2) + 2,
                ),
            )
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - font2.getsize(discount_price)[0]) / 2), 40),
                discount_price,
                font=font2,
                fill=(199, 213, 224),
            )
        else:
            if is_steam:
                original_price = data[i].get("原价")
            elif data[i].get("原价") == "免费开玩":
                original_price = "免费开玩"
            elif "获取失败" in data[i].get("原价"):
                original_price = "获取失败"
            else:
                original_price = "¥" + data[i].get("原价")
            temp_font = resize_font(12, original_price, 55)
            draw_game_bgbar.text(
                (math.ceil(445 + (55 - temp_font[1]) / 2), math.ceil(30 - temp_font[2] / 2)),
                original_price,
                font=temp_font[0],
                fill=(199, 213, 224),
            )

        background.paste(game_bgbar, (10, start_pos + 60 * i + 10 * (i + 1)))

    b_io = io.BytesIO()
    background.save(b_io, format="JPEG")
    base64_str = "base64://" + base64.b64encode(b_io.getvalue()).decode()
    return base64_str


def sell_remind_group(groupid, add: bool):
    data = {}
    if not os.path.exists(os.path.join(FILE_PATH, "data/sell_remind_group.txt")):
        with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "w", encoding="utf-8") as f:
            data["groupid"] = []
            f.write(json.dumps(data, ensure_ascii=False))
    with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "r", encoding="utf-8") as f:
        data = json.loads(f.read())
    groupid_list = data["groupid"]
    if add:
        groupid_list.append(groupid)
        data["groupid"] = groupid_list
    if not add:
        data["groupid"].remove(groupid)
    with open(os.path.join(FILE_PATH, "data/sell_remind_group.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False))


# 小黑盒爬虫
def hey_box(page: int):
    url = f"https://api.xiaoheihe.cn/game/web/all_recommend/games/?os_type=web&version=999.0.0&show_type=discount&limit=30&offset={str((page - 1) * 30)}"
    json_page = json.loads(other_request(url, headers=header).text)
    result_list = json_page["result"]["list"]
    result = []
    for i in result_list:
        lowest_stat = "无当前是否史低信息"
        heybox_price = i.get("heybox_price")
        is_lowest = heybox_price.get("is_lowest", "无信息") if heybox_price else i["price"].get("is_lowest", "无信息")
        discount = heybox_price.get("discount", "0") if heybox_price else i["price"].get("discount", "0")
        gameinfo = {
            "appid": str(i["appid"]),
            "链接": f"https://store.steampowered.com/app/{str(i['appid'])}", 
            "图片": i["game_img"],
            "标题": i["game_name"],
            "原价": str(i["price"]["initial"]) if "price" in i else "无原价信息",
            "当前价": str(i["price"]["current"]) if "price" in i else "无当前价格信息", 
            "平史低价": str(i["price"].get("lowest_price", "无平史低价格信息")),
            "折扣比": discount,  
            "是否史低": lowest_stat,
            "是否新史低": "好耶!是新史低!" if is_lowest == 1 else " ",
            "截止日期": i["price"].get("deadline_date", "无截止日期信息"),
        }
        result.append(gameinfo)
    return result


# 小黑盒搜索爬虫
def hey_box_search(game_name: str):
    url = f"https://api.xiaoheihe.cn/game/search/?os_type=web&version=999.0.0&q={game_name}"
    json_page = json.loads(other_request(url, headers=header).text)
    game_result = json_page["result"]["games"]
    result = []
    for i in game_result:
        gameinfo = {}
        platform = i.get("platforms", "")
        if "steam" in platform:
            if i.get("is_free"):
                gameinfo = {
                    "appid": str(i["steam_appid"]),
                    "链接": f"https://store.steampowered.com/app/{str(i['steam_appid'])}",
                    "原价": "免费开玩",
                    "标题": i["name"],
                    "图片": i["image"],
                    "其他平台图片": i["image"],
                    "平台": platform,
                }
                result.append(gameinfo)
                continue
            if i.get("price", "") != "":
                original = i["price"]["initial"]
                current = i["price"]["current"]
                if original != current:
                    discount = i["price"]["discount"]
                    lowest_state = "是史低哦" if i["price"]["is_lowest"] == 1 else "不是史低哦"
                    newlowest = "好耶!是新史低!" if i["price"].get("new_lowest", "") == 1 else " "
                    deadline = i["price"].get("deadline_date", "无截止日期信息")
                else:
                    discount = "当前无打折信息"
                    lowest_state = newlowest = deadline = " "
                gameinfo = {
                    "appid": str(i["steam_appid"]),
                    "链接": f"https://store.steampowered.com/app/{str(i['steam_appid'])}",
                    "原价": original,
                    "当前价": current,
                    "折扣比": discount,
                    "是否史低": lowest_state,
                    "是否新史低": newlowest,
                    "截止日期": deadline,
                    "平史低价": str(i["price"].get("lowest_price", "无平史低价格信息")),
                    "标题": i["name"],
                    "图片": i["image"],
                    "其他平台图片": i["image"],
                    "平台": platform,
                }
            else:
                gameinfo = {
                    "appid": str(i["steam_appid"]),
                    "链接": f"https://store.steampowered.com/app/{str(i['steam_appid'])}",
                    "原价": "获取失败!可能为免费游戏",
                    "标题": i["name"],
                    "图片": i["image"],
                    "其他平台图片": i["image"],
                    "平台": platform,
                }
        else:
            gameinfo = {
                "appid": str(i["steam_appid"]),
                "链接": f"https://www.xiaoheihe.cn/games/detail/{str(i['steam_appid'])}",
                "标题": i["name"],
                "图片": i["image"],
                "其他平台图片": i["image"],
                "平台": "非steam平台,不进行解析,请自行查看链接",
            }
        result.append(gameinfo)

    return result

def mes_creater_heihe(result, gamename):
    mes_list = []
    if result[0].get("平台", "") == "":
        content = f"    ***数据来源于小黑盒官网***\n***默认展示小黑盒steam促销页面***"
        for i in range(len(result)):
            mes = (
                f"[CQ:image,file={result[i]['图片']}]\n{result[i]['标题']}\n原价:¥{result[i]['原价']} \
                当前价:¥{result[i]['当前价']}(-{result[i]['折扣比']}%)\n平史低价:¥{result[i]['平史低价']} {result[i]['是否史低']}\n链接:{result[i]['链接']}\
                \n{result[i]['截止日期']}(不一定准确,请以steam为准)\n{result[i]['是否新史低']}\nappid:{result[i]['appid']}".strip()
                .replace("\n ", "")
                .replace("    ", "")
            )
            data = {"type": "node", "data": {"name": "sbeam机器人", "uin": "2854196310", "content": mes}}
            mes_list.append(data)
    else:
        content = f"***数据来源于小黑盒官网***\n游戏{gamename}搜索结果如下"
        for i in range(len(result)):
            if "非steam平台" in result[i]["平台"]:
                mes = f"[CQ:image,file={result[i]['其他平台图片']}]\n{result[i]['标题']}\n{result[i]['平台']}\n{result[i]['链接']} (请在pc打开,在手机打开会下载小黑盒app)".strip().replace(
                    "\n ", ""
                )
            elif "免费" in result[i]["原价"]:
                mes = mes = (
                    f"[CQ:image,file={result[i]['图片']}]\n{result[i]['标题']}\n原价:{result[i]['原价']}\n链接:{result[i]['链接']}\nappid:{result[i]['appid']}".strip()
                    .replace("\n ", "")
                    .replace("    ", "")
                )
            elif result[i]["折扣比"] == "当前无打折信息":
                mes = (
                    f"[CQ:image,file={result[i]['图片']}]\n{result[i]['标题']}\n{result[i]['折扣比']}\n当前价:¥{result[i]['当前价']} \
                        平史低价:¥{result[i]['平史低价']}\n链接:{result[i]['链接']}\nappid:{result[i]['appid']}".strip()
                    .replace("\n ", "")
                    .replace("    ", "")
                )
            else:
                mes = (
                    f"[CQ:image,file={result[i]['图片']}]\n{result[i]['标题']}\n原价:¥{result[i]['原价']} 当前价:¥{result[i]['当前价']}\
                        (-{result[i]['折扣比']}%)\n平史低价:¥{result[i]['平史低价']} {result[i]['是否史低']}\n链接:{result[i]['链接']}\n\
                            {result[i]['截止日期']}\n{result[i]['是否新史低']}\nappid:{result[i]['appid']}".strip()
                    .replace("\n ", "")
                    .replace("    ", "")
                )
            data = {"type": "node", "data": {"name": "sbeam机器人", "uin": "2854196310", "content": mes}}
            mes_list.append(data)
    announce = {"type": "node", "data": {"name": "sbeam机器人", "uin": "2854196310", "content": content}}
    mes_list.insert(0, announce)
    return mes_list

@bot.on_message()
async def query_sell_info(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] 查询促销" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        if mes.startswith("查询促销"):
            try:
                sell_info = steam_monitor()
            except Exception as e:
                print(f"Error:{traceback.format_exc()}")
                return
            sell_name = sell_info[0].split(":")[0]
            if "正在进行中" in sell_info[0].split(":")[1]:
                sell_time = f"正在进行中(预计{sell_info[1]}后结束)"
            elif "结束" in sell_info[1]:
                sell_time = f"{sell_info[1]}"
            else:
                sell_time = f"预计{sell_info[1]}后开始"
            await bot.send(event, message=f"{sell_name}:{sell_time}")

@bot.on_message()
async def sell_remind(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] 查询当前促销信息" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        print(mes)
        if mes.startswith("查询当前促销信息"):
            try:
                if sell_remind_data_from_steam:
                    try:
                        data = steam_crawler(url_specials)
                        steam = True
                    except:
                        data = hey_box(1)
                        steam = False
                else:
                    try:
                        data = hey_box(1)
                        steam = False
                    except:
                        data = steam_crawler(url_specials)
                        steam = True
                try:
                    await bot.api.send_group_msg(
                        group_id=group_id, message=f"[CQ:image,file={pic_creater(data, is_steam=steam, monitor_on=True)}]", auto_escape=False, self_id=event.self_id
                    )
                except Exception as e:
                    print(f"每日促销提醒出错,报错内容为:{traceback.format_exc()}")
            except Exception:
                print(f"每日促销提醒出错,报错内容为:{traceback.format_exc()}")


@bot.on_message()
async def heybox(event: Event):
    if event.message_type == 'group' and "[CQ:at,qq=2272628106] 小黑盒" in event.raw_message:
        mes = event.message[event.message.index(']') + 1:].strip()
        if mes.startswith("小黑盒"):
            gamename = ""
            try:
                if "特惠" in mes:
                    data = hey_box(1)
                elif "搜" in mes:
                    index = mes.index('搜')
                    gamename = mes[index+1:]
                    data = hey_box_search(gamename)
                    if len(data) == 0:
                        await bot.api.send(event, "无搜索结果")
                        return
                else:
                    return
            except Exception as e:
                print(f"Error:{traceback.format_exc()}")
            try:
                if send_pic_mes:
                    await bot.api.send(event, f"[CQ:image,file={pic_creater(data, is_steam=False)}]")
                    return
                await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater_heihe(data, gamename))
            except Exception as err:
                if "retcode=100" in str(err):
                    try:
                        if send_pic_mes:
                            await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater_heihe(data, gamename))
                            return
                        await bot.api.send_group_forward_msg(group_id=group_id, messages=mes_creater_heihe(data, gamename))
                    except Exception as err:
                        if "retcode=100" in str(err):
                            await bot.api.send(event, "消息可能依旧被风控,无法完成发送!")
                else:
                    print(f"Error:{traceback.format_exc()}")
# 机器人运行的地址需和Config.yaml文件内的反向代理地址一致，否则机器人将无法收到gocqhttp发送的消息。
if __name__ == '__main__':
    bot.run(host='127.0.0.1', port=5702)


