#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
清水河畔论坛命令行客户端 - 简化版（仅登录功能）
内嵌WebAPI核心登录功能
"""

import argparse
import getpass
import sys
import requests
from bs4 import BeautifulSoup
import os
import json
import warnings


class HepanException(Exception):
    """
    当因为论坛自身限制，导致函数失败时，会抛出此异常
    """

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WebAPI:
    """
    河畔网页API - 精简版（仅包含登录相关功能）
    """
    formhash = ''

    def __init__(self, username=None, password=None, autoLogin=True):
        """
        初始化
        :param username: 用户名
        :param password: 密码
        :param autoLogin: 是否在初始化后自动登录，默认True
        """
        self.username = username
        self.password = password
        self.session = requests.Session()
        
        # 尝试加载保存的cookie（仅在有文件且有效时才加载）
        if os.path.exists('cookies.json') and os.path.getsize('cookies.json') > 0:
            self.load_cookies()
        
        if autoLogin and username and password:
            self.login()
        elif autoLogin:
            # 检查现有会话是否有效
            if self.check_login_status():
                print("已进入主页")
            else:
                raise Exception("Cookie已失效或不存在")

    def login(self):
        """
        登录并自动更新 authorization

        :return:
            成功 True，失败 False
        :raises:
            HepanException: 账号密码错误或账号被限制
        :warning: 连续登录失败5次会被限制登录，请仔细核对用户名和密码
        """
        url = 'https://bbs.uestc.edu.cn/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1'
        data = {'loginfield': 'username', 'username': self.username, 'password': self.password}
        try:
            r = self.session.post(url, data=data, timeout=10)
            r.raise_for_status()
            if '欢迎您回来' in r.text:
                self.save_cookies()  # 保存cookie
                return True and self.update_authorization()
            else:
                raise HepanException(f'登录失败 username={self.username}, password={self.password}\n{r.text}')
        except Exception as e:
            if isinstance(e, HepanException):
                raise
            else:
                print(e)
                return False

    def update_authorization(self):
        """
        更新 authorization

        :return:
            bool: 成功 True，失败 False
        """
        url = 'https://bbs.uestc.edu.cn/star/api/v1/auth/adoptLegacyAuth'
        headers = {'X-Uestc-Bbs': '1'}
        try:
            r = self.session.post(url, headers=headers)
            r.raise_for_status()
            authorization = r.json()['data']['authorization']
            self.session.headers.update({"Authorization": authorization})
            return True
        except Exception as e:
            print(e)
            return False

    def check_login_status(self):
        """
        检查登录状态是否有效

        :return:
            bool: 有效 True，失效 False
        """
        try:
            url = 'https://bbs.uestc.edu.cn'
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            # 检查是否包含用户相关的关键信息
            return '欢迎您回来' in r.text or '退出' in r.text or '用户面板' in r.text
        except:
            return False

    def get_index_data(self):
        """
        获取首页信息

        :return:
            dict: 首页数据
        """
        url = 'https://bbs.uestc.edu.cn/star/api/v1/index'
        params = {
            'global_stat': '1',
            'announcement': '1',
            'forum_list': '1',
            'top_list': 'newreply,newthread,digest,life,hotlist'
        }
        
        # 添加必要的请求头，模拟浏览器请求
        headers = {
            'X-Uestc-Bbs': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        
        try:
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            # 保存响应数据到文件以便查看
            with open('index_data.json', 'w', encoding='utf-8') as f:
                f.write(r.text)
            return r.json()
        except Exception as e:
            print(f"获取首页信息失败: {e}")
            return None

    def get_latest_threads(self, sort_type="new", limit=10):
        """
        获取最新帖子列表

        :param sort_type: 排序类型 ("new" 最新发表, "reply" 最新回复)
        :param limit: 获取帖子数量
        :return: 帖子列表
        """
        url = 'https://bbs.uestc.edu.cn/star/api/v1/thread/list'
        params = {
            'sort': sort_type,
            'limit': limit
        }
        
        # 添加必要的请求头
        headers = {
            'X-Uestc-Bbs': '1'
        }
        
        try:
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"获取{sort_type}帖子列表失败: {e}")
            return None

    def display_index_data(self, data):
        """
        显示首页信息

        :param data: 首页数据
        """
        if not data or data.get('code') != 0:
            print("获取首页数据失败")
            return

        print("\n========== 清水河畔论坛首页 ==========")
        
        # 显示全局统计信息
        global_stat = data['data'].get('global_stat')
        if global_stat:
            print(f"今日帖子数: {global_stat.get('today_posts', 0)} | 昨日帖子数: {global_stat.get('yesterday_posts', 0)} | 总帖子数: {global_stat.get('total_posts', 0)} | 总用户数: {global_stat.get('total_users', 0)}")
        
        # 显示公告信息
        announcements = data['data'].get('announcement', [])
        if announcements:
            print("\n========== 河畔公告 ==========")
            for announcement in announcements[:5]:  # 只显示前5个公告
                title = announcement.get('title', '无标题')
                print(f"- {title}")
        
        # 使用WebAPI获取最新回复和最新发表
        try:
            top_posts = self.get_top_posts()
            if top_posts:
                print("\n========== 最新动态 ==========")
                new_reply_list = top_posts.get('new_reply', [])
                new_thread_list = top_posts.get('new_post', [])
                
                # 显示最新回复
                print("最新回复:")
                for i in range(min(len(new_reply_list), 10)):  # 最多显示10条
                    if i < len(new_reply_list):
                        reply_thread = new_reply_list[i]
                        reply_title = reply_thread.get('title', '无标题')
                        print(f"{i+1:2d}. {reply_title}")
                
                # 显示最新发表
                print("\n最新发表:")
                for i in range(min(len(new_thread_list), 10)):  # 最多显示10条
                    if i < len(new_thread_list):
                        new_thread = new_thread_list[i]
                        thread_title = new_thread.get('title', '无标题')
                        print(f"{i+1:2d}. {thread_title}")
            else:
                print("\n========== 最新动态 ==========")
                print("暂无最新动态")
        except Exception as e:
            print(f"\n获取最新动态失败: {e}")
            print("\n========== 最新动态 ==========")
            print("暂无最新动态")
        
        # 显示板块列表
        forum_list = data['data'].get('forum_list')
        if forum_list:
            print("\n========== 论坛板块 ==========")
            for forum in forum_list:
                print(f"板块: {forum.get('name')} (ID: {forum.get('fid')})")
                # 显示子板块
                children = forum.get('children')
                if children:
                    for child in children:
                        print(f"  └─ {child.get('name')} (ID: {child.get('fid')})")
        
        print("\n========== 首页信息获取完成 ==========")
    
    def get_top_posts(self):
        """
        通过访问主页获取最新帖子信息
        
        :return: 包含最新回复和最新发表等信息的字典
        """
        try:
            # 使用会话访问主页
            url = 'https://bbs.uestc.edu.cn'
            r = self.session.get(url)
            r.raise_for_status()
            
            # 解析页面内容获取最新帖子
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            
            modes = {
                'new_reply': 'portal_block_66_content',  # 最新回复
                'new_post': 'portal_block_67_content'    # 最新发表
            }
            
            result = {}
            for key, target in modes.items():
                element = soup.find(id=target)
                if element:
                    li_elements = element.find_all('li')
                    temp = []
                    for li in li_elements:
                        a_title = li.find('a', title=True)
                        if a_title:
                            title = a_title['title']
                            # 尝试获取帖子链接中的tid
                            href = a_title.get('href', '')
                            tid = 0
                            if 'tid=' in href:
                                tid = int(href.split('tid=')[1].split('&')[0])
                            temp.append({
                                'tid': tid,
                                'title': title
                            })
                    result[key] = temp
                else:
                    result[key] = []
            
            return result
        except Exception as e:
            print(f"获取最新帖子信息失败: {e}")
            return None

    def save_cookies(self):
        """
        保存cookies到文件
        """
        try:
            with open('cookies.json', 'w') as f:
                json.dump(requests.utils.dict_from_cookiejar(self.session.cookies), f)
        except Exception as e:
            print(f"保存cookies失败: {e}")

    def load_cookies(self):
        """
        从文件加载cookies
        """
        try:
            with open('cookies.json', 'r') as f:
                cookies = json.load(f)
                self.session.cookies = requests.utils.cookiejar_from_dict(cookies)
        except Exception as e:
            # 只有在文件存在但内容无效时才打印错误
            if os.path.getsize('cookies.json') > 0:
                print(f"加载cookies失败: {e}")


def main():
    # 先尝试不带参数初始化
    try:
        api = WebAPI(autoLogin=True)
        # 登录成功后获取首页信息
        index_data = api.get_index_data()
        if index_data:
            api.display_index_data(index_data)
    except Exception as e:
        if "Cookie已失效或不存在" in str(e):
            print("Cookie已失效或不存在")
            # 要求输入用户名和密码
            username = input("请输入用户名: ")
            
            # 忽略getpass的警告
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                password = getpass.getpass("请输入密码: ")
            
            try:
                print("正在登录...")
                api = WebAPI(username, password, autoLogin=True)
                print(f"登录成功！欢迎 {username}")
                
                # 登录成功后获取首页信息
                index_data = api.get_index_data()
                if index_data:
                    api.display_index_data(index_data)
            except HepanException as e:
                print(f"登录失败: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"发生错误: {e}")
                sys.exit(1)
        else:
            print(f"发生错误: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()