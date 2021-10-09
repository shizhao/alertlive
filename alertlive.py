#TODO： 运行状态监控

from pywikibot.comms.eventstreams import EventStreams
import pywikibot

import re,time,json
import datetime
import os

import alert_config

site = pywikibot.Site()

#解析streams中的分类数据（添加或移除），返回dict数据
def categorize(matchObj,change):
    dict ={}
    dict['title'] = matchObj.group(1)
    dict['user'] = change['user']
    dict['date'] =  time.strftime("%Y-%m-%d",time.localtime(change['timestamp']))
    dict['action'] = matchObj.group(2)
    dict['category'] = change['title']
    dict['reason'] = ''
    #print(change)
    return dict
    
def logdata(change):
    dict ={}
    dict['title'] = change['title']
    dict['user'] = change['user']
    dict['date'] =  time.strftime("%Y-%m-%d",time.localtime(change['timestamp']))
    dict['action'] = change['log_action']
    dict['reason'] = change['log_action_comment']
    dict['id'] = change['log_id']
    #print(change)
    return dict

#得到某个页面的对话页
def talkpage(site,title):
    page = pywikibot.Page(site, title)
    if page.isTalkPage():
        talk = page
    else:
        talk = pywikibot.Page(site, title).toggleTalkPage()
    return talk

#加载alert_data.json
def load_alertdata():
    with open('./alert_data/alert_data.json', 'r') as f:
        data = json.load(f)
    return data

#加载缓存数据    
def load_cache(file):
    try:
        with open(file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = alert_config.cache_format
    return data

#保存缓存数据
def dump_cache(file,data):
    with open(file, 'w') as f:
        json.dump(data, f)

#获得对话页上已启用alert通知的WPJ横幅模板，返回一个列表。即是对alert_data.json的筛选
def WPJcheck(site,title):
    data = load_alertdata()
    talk = talkpage(site,title)
    talk_template = talk.templates()
    list = []
    #print(talk_template)
    for d in data:
        if pywikibot.Page(site, d[0]) in talk_template: #横幅模板是否在对话页
            list.append(d)
    return list

#根据存档时间参数清理缓存数据
def dateclean(cache,archivetime):
    now = datetime.datetime.now()
    n = 0
    for k,v in cache.items():
        for dict in v:
            diff = (now - datetime.datetime.strptime(dict['date'],"%Y-%m-%d")).days
            if diff > archivetime:
                n+=1
                v.remove(dict)
    if n == 0:
        summary =None
    else:
        summary = '，'+ str(n) + '项已存档'
    return (cache,summary)

def alertcheck(alert_page):
    alert_data = load_alertdata()
    data_str = json.dumps(alert_data)
    for data in alert_data:
        if data[1]['alert_page'] == alert_page:
            alert_template = pywikibot.Page(site, u"Template:ArticleAlertbot")
            templates_Params = pywikibot.Page(site, alert_page).templatesWithParams()
            #print(templates_Params)
            for Params_tuple in templates_Params:
                if Params_tuple[0] == alert_template: #Params_tuple:  (Page('Template:ArticleAlertbotSubscription'), ['sub=條目狀態通告'])
                    for Params in Params_tuple[1]:
                        
                        if Params[:7] == 'banner=' and len(Params) > 7:
                            banner = 'Template:' + Params[7:]
                            if banner != data[0]:
                                data[0] = banner
                        elif Params[:12] == 'archivetime=' and len(Params) > 12 and Params[12:].isdigit():
                            archivetime = int(Params[12:])
                            if archivetime != data[1]['archivetime']:
                                data[1]['archivetime'] = archivetime
                        elif Params[:10] == 'workflows=' and len(Params) > 10:
                            workflows = Params[10:].replace(' ','').lower()
                            workflows_list = workflows.split(',')
                            if 'all' in workflows_list:
                                workflows_list = ['all']
                            if workflows_list != data[1]['workflows']:
                                data[1]['workflows'] = workflows_list
    if cachestr != json.dumps(alert_data):              
        print('UPDATE: ',alert_data)
        with open('./alert_data/alert_data.json', 'w') as f:
            json.dump(alert_data, f)      

def post2wiki(alert_page,workflows,cache,summary):
    #todo
    text_head ='\n'
    text =''
    text_foot = '\n最后更新于~~~~~\n<noinclude>{{ArticleAlertbot/foot}}</noinclude>'
    alert_input = {}

    for kk,vv in alert_config.alert_types.items():
        alert_input[kk] = ''
        #text += '\n;'+kk+'\n'
        for k,v in cache.items():
            if k in vv:
                if k.lower() in workflows or workflows[0] == 'all':
                    for item in v:
                        alert_input[kk] += item['wikitext']+'\n'
                        #text += item['wikitext']+'\n'
    for s,c in alert_input.items():
        if c:
            text += '\n;'+s+'\n'+c
    print(summary)
    if text:
        wikipage = pywikibot.Page(site,alert_page)
        wikitext = wikipage.text
        try:
            text_head = re.match(r'(?P<head>\{\{ArticleAlertbot.*?\}\})',wikitext,re.M|re.S).group('head') + text_head
        except AttributeError as e:
            print(e)
        #try:
        #    text_foot += re.match(r'(?P<foot>\{\{ArticleAlertbot\/foot.*?\}\})',wikitext,re.M|re.S).group('foot')
        #except AttributeError as e:
        #    print(e)
        text = text_head + text + text_foot
        print(text)
        #wikipage.text = text
        #wikipage.save(summary)
    else:
        print('workflows参数没有使用规定值')

#对分类改变的数据进行处理
def process_catdata(site,stream_data,alert_type,wikitextformat,summary='',templates=None,subtype=None,with_talk=False):
    #解析分类中数据
    title = stream_data['title']
    talk = talkpage(site,title)
    #print(talk)
    if talk.exists() and not talk.isRedirectPage():
        #从对话页获取WPJ模板
        wpjdata = WPJcheck(site,title)
        if wpjdata:
            
            print(wpjdata)
            for wpj in wpjdata:
                #alerts_cache = alert_config.cache_format
                stream_data['type'] = subtype
                #stream_data['reason'] = ''
                if templates:
                    for tuple in pywikibot.Page(site, title).templatesWithParams():
                        if tuple[0].title() in templates:
                            stream_data['reason'] = '，'.join(list(map(lambda str: str[str.find('=')+1:], tuple[1])))
                if pywikibot.Page(site, title).isTalkPage() and with_talk: 
                    stream_data['title'] = pywikibot.Page(site, title).toggleTalkPage().title()
                stream_data['wikitext'] = wikitextformat.format(**stream_data)
                alert_page = wpj[1]['alert_page']
                workflows = wpj[1]['workflows']
                archivetime = wpj[1]['archivetime']
                jsonfile = wpj[1]['jsonfile']
                cache = load_cache('./alert_data/'+jsonfile)
                try:
                    cache_type= cache[alert_type]
                except KeyError:
                    cache[alert_type] = []
                    cache_type= cache[alert_type]
                    
                if cache_type:
                    cache_copy = cache_type.copy()
                    n=0
                    for i in range(len(cache_copy)):
                        if cache_type[i]['title'] == stream_data['title']:
                            cache_type[i] = stream_data
                        else:
                            n+=1
                    if len(cache_copy) == n:
                        cache_type.insert(0,stream_data)
                else:
                    cache_type.insert(0,stream_data)
                cache = dateclean(cache,archivetime)[0]
                archive_summary = dateclean(cache,archivetime)[1]
                if archive_summary:
                    summary += dateclean(cache,archivetime)[1]
                print(stream_data)
                print(jsonfile,cache)
                dump_cache('./alert_data/'+jsonfile,cache)
                alertcheck(alert_page) #每次更新时检查alert模板的参数有无变化
                post2wiki(alert_page,workflows,cache,summary)

#对分类改变的处理，弃用   
def changecat(site,change,alert_type,subtype=None):
    add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
    remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
    #加入分类
    if add_matchObj:
        process_catdata(site,add_matchObj,change,alert_type,subtype)
    #移除分类
    elif remove_matchObj:
        process_catdata(site,remove_matchObj,change,alert_type,subtype)
    else:
        print('Cannot match the comment text in categorize: %s' % change['comment'])

#==========================MAIN=============================
stream = EventStreams(streams=['recentchange'])
stream.register_filter(wiki='zhwiki',type=('categorize', 'log'))
while True:
    change = next(iter(stream))
    #print('{type} on page "{title}" by "{user}" at {meta[dt]}.'.format(**change))
    #根据分类改变来识别的alert
    if change['type'] == 'categorize':
    
        #================alert页面=======================
        if change['title'] == alert_config.alertcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                alert_data = load_alertdata()
                alert_template = pywikibot.Page(site, u"Template:ArticleAlertbot")
                templates_Params = pywikibot.Page(site, add_matchObj.group(1)).templatesWithParams()
                #print(templates_Params)
                for Params_tuple in templates_Params:
                    if Params_tuple[0] == alert_template: #Params_tuple:  (Page('Template:ArticleAlertbotSubscription'), ['sub=條目狀態通告'])
                        params_data = {}
                        banner = ''
                        archivetime = 30
                        workflows_list = ['all']
                        for Params in Params_tuple[1]:
                            
                            if Params[:7] == 'banner=' and len(Params) > 7:
                                banner = 'Template:' + Params[7:]
                                #params_data['banner'] = banner

                            elif Params[:12] == 'archivetime=' and len(Params) > 12 and Params[12:].isdigit():
                                archivetime = int(Params[12:])
                            elif Params[:10] == 'workflows=' and len(Params) > 10:
                                workflows = Params[10:].replace(' ','').lower()
                                workflows_list = workflows.split(',')
                                if 'all' in workflows_list:
                                    workflows_list = ['all']
                            
                        if banner and pywikibot.Page(site, banner).exists():
                            params_data['alert_page'] = add_matchObj.group(1)
                            params_data['archivetime'] = archivetime
                            params_data['workflows'] = workflows_list
                            params_data['jsonfile'] = add_matchObj.group(1).replace('/','_')+'.json'
                            alert_data.append((banner, params_data))
                            with open('./alert_data/alert_data.json', 'w') as f:
                                json.dump(alert_data, f)
                print(change)
                print(alert_data)

            #移除分类
            elif remove_matchObj:
                alert_data = load_alertdata()
                for data in alert_data:
                    if data[1]['alert_page'] == remove_matchObj.group(1):
                        alert_data.remove(data)
                        print(change)
                        print(alert_data)
                        with open('./alert_data/alert_data.json', 'w') as f:
                            json.dump(alert_data, f)                
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================CSD=======================
        if change['title'] == alert_config.csdcat:
            #changecat(site,change,'CSD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{reason}|速删}}}}'
                summary = '速删：+[[' + add_matchObj.group(1) + ']]'
                process_catdata(site,categorize(add_matchObj,change),'CSD',wikitextformat,summary,templates = ['Template:Delete'])
            #移除分类
            elif remove_matchObj:
                summary = '速删：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isCategoryRedirect():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getCategoryRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}}}}}改为消歧义页'
                else:               
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'CSD',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])
            # Todo：{{hang on|理由}}，现缺少专门分类

        #================FCSD文件速删(与CSD合并)=======================        
        elif change['title'] in alert_config.filecsd_cats:
            #changecat(site,change,'FCSD',subtype=change['title'].split(':',1)[1])
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                #{{SetTitle|Hyper Text Markup Language|HTML}}
                summary = '文件速删：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{type}|速删}}}}'
                process_catdata(site,categorize(add_matchObj,change),'CSD',wikitextformat,summary,subtype=change['title'].split(':',1)[1])
            #移除分类
            elif remove_matchObj:
                summary = '文件速删：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交{{{{SetTitle|{type}|速删}}}}后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'CSD',wikitextformat,summary,subtype=change['title'].split(':',1)[1])
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================VFD======================= 
        #todo: 讨论位置，计票
        elif change['title'] in alert_config.vfdcat:
            #changecat(site,change,'VFD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '存废：+[[' + add_matchObj.group(1) + ']]'
                vfdtemplate = ['Template:Vfd','Template:Afd','Template:Cfd','Template:Tfd','Template:Ufd','Template:Mfd','Template:Rfd']
                templates_Params = pywikibot.Page(site, add_matchObj.group(1)).templatesWithParams()
                vfddate = ''
                for Params_tuple in templates_Params:
                    if Params_tuple[0].title() in vfdtemplate: 
                        for p in Params_tuple[1]:
                            if p.split('=',1)[0].lower() == 'date':
                                vfddate = p.split('=',1)[1]
                if vfddate:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{reason}|存废讨论}}}} -> [[Wikipedia:頁面存廢討論/記錄/%s#%s|参与讨论]]' % (vfddate, add_matchObj.group(1))
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{reason}|存废讨论}}}}'
                process_catdata(site,categorize(add_matchObj,change),'VFD',wikitextformat, summary,vfdtemplate)
            #移除分类
            elif remove_matchObj:
                #todo：保留的不同形式：合并等
                summary = '存废：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isCategoryRedirect():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getCategoryRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}}}}}改为消歧义页'
                else:               
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'VFD',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================IFD（与VFD合并）=======================    
        #todo: 讨论位置，计票
        elif change['title'] == alert_config.ifdcat:
            #changecat(site,change,'IFD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '文件删除：+[[' + add_matchObj.group(1) + ']]'
                ifdtemplate = 'Template:Ifd'
                templates_Params = pywikibot.Page(site, add_matchObj.group(1)).templatesWithParams()
                ifddate = ''
                for Params_tuple in templates_Params:
                    if Params_tuple[0].title() == ifdtemplate: 
                        for p in Params_tuple[1]:
                            if p.split('=',1)[0].lower() == 'date':
                                ifddate = p.split('=',1)[1]
                if ifddate:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{reason}|文件删除讨论}}}} -> [[Wikipedia:檔案存廢討論/記錄/%s#%s|参与讨论]]' % (ifddate, add_matchObj.group(1))
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交{{{{SetTitle|{reason}|文件删除讨论}}}}'
                process_catdata(site,categorize(add_matchObj,change),'VFD',wikitextformat,summary,['Template:Ifd'])
            #移除分类
            elif remove_matchObj:
                summary = '文件删除：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交文件删除讨论后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'VFD',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================Transwiki=======================    
        elif change['title'] in alert_config.transwikicat:
            #changecat(site,change,'Transwiki',subtype=change['title'].split(':',1)[1])
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '移动到其他计划：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}建议{type}'
                process_catdata(site,categorize(add_matchObj,change),'TRANS',wikitextformat,summary,subtype=change['title'].split(':',1)[1])
            #移除分类
            elif remove_matchObj:
                summary = '移动到其他计划：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]建议{type}后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'TRANS',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================COPYVIO=======================    
        #todo: 草稿
        elif change['title'] == alert_config.copyviocat:
            #changecat(site,change,'COPYVIO')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '侵权：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}怀疑侵权'
                process_catdata(site,categorize(add_matchObj,change),'COPYVIO',wikitextformat,summary)
            #移除分类
            elif remove_matchObj:
                summary = '侵权：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}解决了侵权问题'
                process_catdata(site,categorize(remove_matchObj,change),'COPYVIO',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================DRV存废复核=======================
        #todo: 讨论位置
        elif change['title'] == alert_config.drvcat:
            #changecat(site,change,'DRV')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '存废复核：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}提交存废复核'
                process_catdata(site,categorize(add_matchObj,change),'DRV',wikitextformat,summary)
            #移除分类
            elif remove_matchObj:
                summary = '存废复核：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交存废复核后被{{{{User|{user}}}}}保留'
                process_catdata(site,categorize(remove_matchObj,change),'DRV',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])
                
        #================DYKC=======================
        elif change['title'] == alert_config.dykccat:
            #changecat(site,change,'DRV')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'DYK：[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]被提名[[Wikipedia:新条目推荐/候选#{title}|新条目推荐候选]]'
                process_catdata(site,categorize(add_matchObj,change),'DYK',wikitextformat,summary,with_talk = True)

        #================DYK=======================
        elif change['title'] == alert_config.dykcat:
            #changecat(site,change,'DRV')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'DYK：+[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已通过新条目推荐 -> [[Talk:{title}#新条目推荐讨论|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'DYK',wikitextformat,summary,with_talk = True)
                
        #================FLC,FLR重选,FLK重选维持=======================
        elif change['title'] == alert_config.flccat:
            #changecat(site,change,'DRV')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FL：[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:Featured list removal candidates') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:特色列表评选#{title}|重选特色列表]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:特色列表评选#{title}|评选特色列表]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
            elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:Featured list') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'FL：[[' + remove_matchObj.group(1).split(':',1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了特色列表状态 -> [[Talk:{title}|讨论存档]]'           
                    process_catdata(site,categorize(remove_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])
                
        #================FL=======================
        elif change['title'] == alert_config.flcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FL：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:特色列表|特色列表]] -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary)
                
        #================FLFailed落选=======================
        elif change['title'] == alert_config.flfcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FL：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]评选特色列表失败 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
                
        #================FFL撤销=======================
        elif change['title'] == alert_config.fflcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FL：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已撤销特色列表状态 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
                
        #================FAC，FAR，FAK=======================
        elif change['title'] == alert_config.faccat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FA：[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:Featured article review') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:典范条目评选#{title}|重选典范条目]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:典范条目评选#{title}|评选典范条目]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
            elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:Featured article') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'FA：+[[' + remove_matchObj.group(1).split(':',1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了典范条目状态 -> [[Talk:{title}|讨论存档]]'           
                    process_catdata(site,categorize(remove_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment']) 

        #================FA=======================
        elif change['title'] == alert_config.facat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FA：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:典范条目|典范条目]] -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary)

        #================FAF落选=======================
        elif change['title'] == alert_config.fafcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FA：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]评选典范条目失败 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)

        #================FAL撤销=======================
        elif change['title'] == alert_config.falcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'FA：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已撤销典范条目状态 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'FC',wikitextformat,summary,with_talk = True)
            
        #================GAN,GAR,GAK=======================
        elif change['title'] == alert_config.gancat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'GA：[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:GA reassessment') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:優良條目評選#{title}|重选优良条目]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]正在[[Wikipedia:優良條目評選#{title}|评选优良条目]]'
                process_catdata(site,categorize(add_matchObj,change),'GA',wikitextformat,summary,with_talk = True)
            elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site,'Template:Good article') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'GA：+[[' + remove_matchObj.group(1).split(':',1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了優良条目状态 -> [[Talk:{title}|讨论存档]]'           
                    process_catdata(site,categorize(remove_matchObj,change),'GA',wikitextformat,summary,with_talk = True)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment']) 

        #================GA=======================
        elif change['title'] == alert_config.gacat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'GA：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:優良条目|優良条目]] -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'GA',wikitextformat,summary)

        #================GAF落选=======================
        elif change['title'] == alert_config.gafcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'GA：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]评选優良条目失败 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'GA',wikitextformat,summary,with_talk = True)

        #================GAL撤销=======================
        elif change['title'] == alert_config.galcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'GA：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已撤销优良条目状态 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'GA',wikitextformat,summary,with_talk = True) 

        #================PR=======================
        elif change['title'] == alert_config.prcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'PR：+[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]正在进行[[Wikipedia:同行评审#{title}|同行评审]]'
                process_catdata(site,categorize(add_matchObj,change),'PR',wikitextformat,summary,with_talk = True)

         #================PR结束=======================
        elif change['title'] == alert_config.predcat:
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            #remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = 'PR：-[[' + add_matchObj.group(1).split(':',1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已结束同行评审 -> [[Talk:{title}|讨论存档]]'
                process_catdata(site,categorize(add_matchObj,change),'PR',wikitextformat,summary,with_talk = True)
                
        #================拆分======================= 
        elif change['title'] == alert_config.splitcat:
            #changecat(site,change,'VFD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '拆分：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}建议拆分'
                process_catdata(site,categorize(add_matchObj,change),'SPLIT',wikitextformat,summary)
            #移除分类
            elif remove_matchObj:
                summary = '拆分：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]已经由{{{{User|{user}}}}}完成拆分'
                process_catdata(site,categorize(remove_matchObj,change),'SPLIT',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])
                
        #================小小作品=======================
        elif change['title'] in alert_config.substubcat:
            #changecat(site,change,'VFD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '小小作品：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}标记为小小作品'
                process_catdata(site,categorize(add_matchObj,change),'SUB',wikitextformat,summary)
            #移除分类
            elif remove_matchObj:
                summary = '小小作品：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}改为消歧义页'
                else:               
                    wikitextformat = '* {date}：[[:{title}]]已经不是小小作品了！'
                process_catdata(site,categorize(remove_matchObj,change),'SUB',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

        #================关注度======================= 
        elif change['title'] in alert_config.notabilitycat:
            #changecat(site,change,'VFD')
            add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '关注度：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}认为缺乏关注度'
                process_catdata(site,categorize(add_matchObj,change),'FAME',wikitextformat,summary)
            #移除分类
            elif remove_matchObj:
                summary = '关注度：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}}}}}改为消歧义页'
                else:               
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}}}}}解决了关注度问题'
                process_catdata(site,categorize(remove_matchObj,change),'FAME',wikitextformat,summary)
            else:
                print('Cannot match the comment text in categorize: %s' % change['comment'])

    if change['type'] == 'log':
        if change['log_type'] == 'delete' and change['log_action'] == 'delete':
            path = './alert_data/'
            alert_data = load_cache('./alert_data/alert_data.json')
            for data in alert_data:
                file = data[1]['jsonfile']
                alert_page = data[1]['alert_page']
                workflows = data[1]['workflows']
                cache = load_cache('./alert_data/'+file)
                cachestr = json.dumps(cache)
                
                for k,v in cache.items():
                    i = 0
                    for dict in v:
                        if dict['title'] == change['title']:
                            summary = '-[[' + change['title'] + ']]已删除'
                            wikitextformat = '* {{{{color|grey|{date}}}}}：[[:{title}]]已被{{{{User|{user}}}}}{{{{SetTitle|{reason}|删除}}}} -> {{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}'
                            stream_data = logdata(change)
                            stream_data['wikitext'] = wikitextformat.format(**stream_data)
                            v[i] = stream_data
                        i+=1
                if cachestr != json.dumps(cache):
                    print(change)
                    print(file,cache)
                    dump_cache('./alert_data/'+file,cache)
                    #wikipage = pywikibot.Page(site,alert_page)
                    alertcheck(alert_page)
                    post2wiki(alert_page,workflows,cache,summary)
                        
        #================保护======================= 
        elif change['log_type'] == 'protect':
            if change['log_action'] == 'protect':
                #todo:编辑请求
                summary = '保护：+[[' + change['title'] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}}}}}{{{{SetTitle|{reason}|保护}}}} -> {{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}'
                process_catdata(site,logdata(change),'PP',wikitextformat,summary,subtype='protect')
            #移除分类
            elif change['log_action'] == 'unprotect':
                summary = '解除保护：-[[' + change['title'] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}}}}}{{{{SetTitle|{reason}|解除保护}}}} -> {{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}'
                process_catdata(site,logdata(change),'PP',wikitextformat,summary,subtype='unprotect')
        #if change['log_type'] == 'move':    
        #    print(change)
            

"""TODO: 
2.合并
3.今日首页（特色，优良，ITN？）
4.新建条目？
5.移动请求

"""
#t = page.templatesWithParams()
"""
{'title': 'Category:移動重定向', 'bot': True, 'server_name': 'zh.wikipedia.org', 'meta': {'partition': 0, 'offset': 3310430515, 'domain': 'zh.wikipedia.org', 'stream': 'mediawiki.recentchange', 'topic': 'eqiad.mediawiki.recentchange', 'id': '8747fb90-de3d-47fd-9a09-5d2bf311532f', 'uri': 'https://zh.wikipedia.org/wiki/Category:%E7%A7%BB%E5%8B%95%E9%87%8D%E5%AE%9A%E5%90%91', 'dt': '2021-09-20T13:10:03Z', 'request_id': '138f3062-477a-4cfc-bcda-4cbd8d844426'}, 'wiki': 'zhwiki', 'parsedcomment': '<a href="/wiki/User:Renbaoshuo" class="mw-redirect" title="User:Renbaoshuo">User:Renbaoshuo</a>已添加至分类', 'server_script_path': '/w', 'user': 'Jimmy Xu', 'namespace': 14, 'timestamp': 1632143403, 'comment': '[[:User:Renbaoshuo]]已添加至分类', 'server_url': 'https://zh.wikipedia.org', '$schema': '/mediawiki/recentchange/1.0.0', 'id': 138715371, 'type': 'categorize'}



User:激鬥峽谷已从分类中移除
"""

"""
[['Template:足球專題', {'alert_page': 'WikiProject:足球/條目狀態', 'jsonfile': 'WikiProject:足球_條目狀態.json', 'workflows': ['all'], 'archivetime': 30}], ['Template:WikiProject Biography', {'alert_page': 'User:Shizhao/test2/1', 'jsonfile': 'User:Shizhao_test2_1.json', 'workflows': ['all'], 'archivetime': 40}]]
{'title': 'User:Shizhao/test3', 'user': 'Shizhao', 'action': '添加', 'date': '2021-09-23'}
"""

"""
{'type': 'log', 'server_url': 'https://zh.wikipedia.org', 'user': 'Qetuoiyrw', 'server_name': 'zh.wikipedia.org', 'timestamp': 1632646446, '$schema': '/mediawiki/recentchange/1.0.0', 'log_action': 'hit', 'namespace': 0, 'log_id': 0, 'log_action_comment': 'Qetuoiyrw 於 [[雲林縣私立淵明國民中學]] 執行操作 "edit" 已觸發 [[Special:滥用过滤器/223|過濾器 223]]。採取的動作：標籤 ([[Special:滥用日志/3934453|詳細資料]])', 'log_params': {'filter': '223', 'action': 'edit', 'log': 3934453, 'actions': 'tag'}, 'parsedcomment': '', 'bot': False, 'meta': {'id': 'eb92d68c-bdbb-4182-ac56-e43c741cb785', 'stream': 'mediawiki.recentchange', 'partition': 0, 'topic': 'eqiad.mediawiki.recentchange', 'dt': '2021-09-26T08:54:06Z', 'request_id': '46efdb15-d7d9-48e7-8721-7ff1dca3c7bc', 'offset': 3323405464, 'domain': 'zh.wikipedia.org', 'uri': 'https://zh.wikipedia.org/wiki/%E9%9B%B2%E6%9E%97%E7%B8%A3%E7%A7%81%E7%AB%8B%E6%B7%B5%E6%98%8E%E5%9C%8B%E6%B0%91%E4%B8%AD%E5%AD%B8'}, 'log_type': 'abusefilter', 'wiki': 'zhwiki', 'title': '雲林縣私立淵明國民中學', 'comment': '', 'server_script_path': '/w'}

"""

"""
{'log_type': 'delete', 'log_action': 'delete', 'log_action_comment': 'deleted &quot;[[舞法天少女朵法拉第七季]]&quot;：[[WP:CSD#G3|G3]]: 纯粹[[WP:VAN|破坏]]，包括但不限于明显的[[WP:HOAX|恶作剧]]、错误信息、[[WP:PA|人身攻击]]等', 'user': 'Shizhao', 'id': 138940549, 'server_script_path': '/w', 'meta': {'domain': 'zh.wikipedia.org', 'partition': 0, 'stream': 'mediawiki.recentchange', 'topic': 'eqiad.mediawiki.recentchange', 'uri': 'https://zh.wikipedia.org/wiki/%E8%88%9E%E6%B3%95%E5%A4%A9%E5%B0%91%E5%A5%B3%E6%9C%B5%E6%B3%95%E6%8B%89%E7%AC%AC%E4%B8%83%E5%AD%A3', 'dt': '2021-09-26T09:08:57Z', 'id': '11f114d4-69ed-451b-a67a-972db14cd7d8', 'request_id': '26d4b058-ebab-41bf-ae48-a5f3c8ed1f61', 'offset': 3323431467}, 'parsedcomment': '<a href="/wiki/Wikipedia:CSD#G3" class="mw-redirect" title="Wikipedia:CSD">G3</a>: 纯粹<a href="/wiki/Wikipedia:VAN" class="mw-redirect" title="Wikipedia:VAN">破坏</a>，包括但不限于明显的<a href="/wiki/Wikipedia:HOAX" class="mw-redirect" title="Wikipedia:HOAX">恶作剧</a>、错误信息、<a href="/wiki/Wikipedia:PA" class="mw-redirect" title="Wikipedia:PA">人身攻击</a>等', 'title': '舞法天少女朵法拉第七季', 'comment': '[[WP:CSD#G3|G3]]: 纯粹[[WP:VAN|破坏]]，包括但不限于明显的[[WP:HOAX|恶作剧]]、错误信息、[[WP:PA|人身攻击]]等', 'bot': False, 'wiki': 'zhwiki', 'type': 'log', 'namespace': 0, 'timestamp': 1632647337, 'log_params': [], '$schema': '/mediawiki/recentchange/1.0.0', 'server_name': 'zh.wikipedia.org', 'server_url': 'https://zh.wikipedia.org', 'log_id': 10844911}

"""

"""
{'type': 'log', 'comment': '机器人: 被永久封禁的用户页', 'id': 138996373, 'server_script_path': '/w', 'wiki': 'zhwiki', 'user': 'Jimmy-abot', 'namespace': 2, 'bot': True, 'parsedcomment': '机器人: 被永久封禁的用户页', 'log_params': {'details': [{'type': 'create', 'expiry': 'infinity', 'level': 'sysop'}], 'cascade': False, 'description': '\u200e[create=sysop] (无限期)'}, 'server_url': 'https://zh.wikipedia.org', 'log_id': 10848695, 'title': 'User:S002282000', '$schema': '/mediawiki/recentchange/1.0.0', 'timestamp': 1632808452, 'server_name': 'zh.wikipedia.org', 'log_action_comment': '保护 User:S002282000 \u200e[create=sysop] (无限期)：机器人: 被永久封禁的用户页', 'meta': {'offset': 3328394438, 'uri': 'https://zh.wikipedia.org/wiki/User:S002282000', 'domain': 'zh.wikipedia.org', 'topic': 'eqiad.mediawiki.recentchange', 'dt': '2021-09-28T05:54:12Z', 'stream': 'mediawiki.recentchange', 'request_id': '292317ad-ca22-4dcd-9e2c-17db5da3da0d', 'id': '07c10791-e6c8-466b-ad8e-37416c534dfa', 'partition': 0}, 'log_action': 'protect', 'log_type': 'protect'}
"""