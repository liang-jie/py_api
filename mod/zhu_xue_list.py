# -*- coding: utf-8 -*-
# 可申请助学金
from cache.ZhuListCache import ZhuListCache
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
import tornado.web
import tornado.gen
import urllib, re
import json
import traceback
from BeautifulSoup import BeautifulSoup
from sqlalchemy.orm.exc import NoResultFound
from time import localtime, strftime, time
from auth import getCookie


class zhu_listHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db
        
    def on_finish(self):
        self.db.close()

    def get(self):
        self.write('hello')

    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        user = self.get_argument('number',default=None)
        password = self.get_argument('password',default=None)

        # read from cache
        try:
            status = self.db.query(ZhuListCache).filter(ZhuListCache.number == user).one()
            if status.date > int(time())-4 and status.text != '*':
                self.write(status.text)
                self.finish()
                return
        except NoResultFound:
            status = ZhuListCache(number = user,text = '*',date = int(time()))
            self.db.add(status)
            try:
                self.db.commit()
            except:
                self.db.rollback()
        BASE_URL = "http://my.seu.edu.cn/index.portal"
        ZHU_LIST_URL = "http://my.seu.edu.cn/index.portal?.pn=p1064_p1067"
        retjson = {'code':200, 'content':''}
        
        try:
            ret = getCookie(self.db,user,password)
            if ret['code'] == 200:
                cookie = ret['content']
                client = AsyncHTTPClient()
                request = HTTPRequest(
                    url = ZHU_LIST_URL,
                    method = "GET",
                    headers = {'Cookie':cookie},
                    request_timeout = 8
                    )
                response = yield client.fetch(request)
                soup = BeautifulSoup(response.body)
                li_item = soup.find('li',{'id':'one2'})
                print li_item['onclick']
                data_url = BASE_URL + li_item['onclick'].split("'")[1]+"&pageIndex=1&pageSize=20"
                print data_url
                split_array = response.headers['Set-Cookie'].split(";")
                cookie = cookie.split(";")[0] + ";" + split_array[0]+";"+split_array[1].split(",")[1]
                request = HTTPRequest(
                    url = data_url,
                    method = "GET",
                    headers = {
                        'Cookie':cookie,
                        'Referer':'http://my.seu.edu.cn/index.portal?.pn=p1064_p1551',
                        'Host':'my.seu.edu.cn'
                        },
                    request_timeout = 8
                    )
                response = yield client.fetch(request)
                data_content = response.body
                retjson['content'] = self.deal_data(response.body)
                # retjson['content'] = response.body
            else:
                retjson = ret
        except Exception,e:
            with open('api_error.log','a+') as f:
                f.write(strftime('%Y%m%d %H:%M:%S in [api]', localtime(time()))+'\n'+str(str(e)+'\n[zhu_list]\t'+str(user)+'\nString:'+str(retjson)+'\n\n'))
            retjson['code'] = 500
            retjson['content'] = 'system error'
        ret = json.dumps(retjson, ensure_ascii=False, indent=2)
        self.write(ret)
        self.finish()

        # refresh cache
        if retjson['code'] == 200:
            status.date = int(time())
            status.text = ret
            self.db.add(status)
            try:
                self.db.commit()
            except Exception,e:
                self.db.rollback()
    def deal_data(self,html):
        soup = BeautifulSoup(html)
        div = soup.findAll('div',{'class':'isp-service-item-content'})
        # div.pop(0)
        ret = []
        for item in div:
            div_item = item.findAll('div',{'class':'jxjInfo'})
            temp = {
                'name':item.find('div',{'class':'jxjTitle'}).text,
                'time':div_item[0].text[3:],
                'type':div_item[1].text[6:],
                'term':div_item[2].text[5:],
                'money':div_item[3].text[3:],
                'number':div_item[4].text[6:]
            }
            ret.append(temp)
        return ret
