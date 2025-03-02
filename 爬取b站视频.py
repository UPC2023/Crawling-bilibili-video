import requests
import json
import re
from pprint import pprint
import os

def download(BV):
    url = f'https://www.bilibili.com/video/{BV}'

    # 设置请求头
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
        "Referer": "https://www.bilibili.com/",  # 设置防盗链
    }

    resp = requests.get(url=url, headers=header)
    if resp.status_code != 200:
        print("Failed to retrieve the webpage.")
        exit()

    # 这个baseUrl就是视频的地址
    obj = re.compile(r'window.__playinfo__=(.*?)</script>', re.S)
    html_data = obj.findall(resp.text)[0]  # 从列表转换为字符串
    json_data = json.loads(html_data)

    # 获取视频和音频地址
    videos = json_data['data']['dash']['video']  # 这里得到的是一个列表
    audios = json_data['data']['dash']['audio']

    if not videos or not audios:
        print("Failed to find video or audio URLs.")
        exit()

    video_url = videos[0]['baseUrl']  # 视频地址
    audio_url = audios[0]['baseUrl']  # 音频地址

    # 获取用户输入的文件名
    name = input("name: ")

    # 下载视频文件
    resp1 = requests.get(url=video_url, headers=header)
    with open(f'{name}.mp4', mode='wb') as f:
        f.write(resp1.content)

    # 下载音频文件
    resp2 = requests.get(url=audio_url, headers=header)
    with open(f'{name}.mp3', mode='wb') as f:
        f.write(resp2.content)

    print("Download complete")

    # 现在需要将视频和音频合并 需要模块ffmpeg 可以在网上看教程
    command = f'ffmpeg -i {name}.mp4 -i {name}.mp3 -acodec copy -vcodec copy {name}_out.mp4'
    os.system(command)

    print("Merge complete")
# 获取用户输入的 BV 号
BV = input("BV: ")
while (BV!="0"):
    download(BV)
    BV = input("BV: ")
