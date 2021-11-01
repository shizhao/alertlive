from pywikibot.comms.eventstreams import EventStreams
import pywikibot
import re
import time
import json
import datetime
import alert_config
import pywikibot.textlib as textlib

site = pywikibot.Site()
site.login()
# 解析streams中的分类数据（添加或移除），返回dict数据


def categorize(matchObj, change, **kwargs):
    dict = {'title': matchObj.group(1),
            'user': change['user'],
            'date': time.strftime(
            "%Y-%m-%d", time.localtime(change['timestamp'])),
            'action': matchObj.group(2),
            'category': change['title'],
            'reason': '',
            'talkat': ''
            }
    if 'talkat' in kwargs:
        dict['talkat'] = kwargs['talkat']
    if 'moveto' in kwargs:
        dict['moveto'] = kwargs['moveto']
    return dict


def logdata(change):
    dict = {
        'title': change['title'],
        'user': change['user'],
        'date': time.strftime(
            "%Y-%m-%d", time.localtime(change['timestamp'])),
        'action': change['log_action'],
        'reason': change['log_action_comment'],
        'id': change['log_id'],
    }
    if 'log_params' in change:
        if 'target' in change['log_params']:
            dict['moveto'] = change['log_params']['target']
    return dict

# 得到某个页面的对话页


def talkpage(site, title):
    page = pywikibot.Page(site, title)
    if page.isTalkPage():
        talk = page
    else:
        talk = pywikibot.Page(site, title).toggleTalkPage()
    return talk

# 加载alert_data.json


def load_alertdata():
    with open('./alert_data/alert_data.json', 'r') as f:
        data = json.load(f)
    return data

# 加载缓存数据


def load_cache(file):
    try:
        with open(file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = alert_config.cache_format
    return data

# 保存缓存数据


def dump_cache(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

# 获得对话页上已启用alert通知的WPJ横幅模板，返回一个列表。即是对alert_data.json的筛选


def WPJcheck(site, title):
    data = load_alertdata()
    talk = talkpage(site, title)
    talk_template = talk.templates()
    list = []
    for d in data:
        if pywikibot.Page(site, d[0]) in talk_template:  # 横幅模板是否在对话页
            list.append(d)
    return list

# 根据存档时间参数清理缓存数据


def dateclean(cache, archivetime):
    now = datetime.datetime.now()
    n = 0
    for k, v in cache.items():
        for dict in v:
            diff = (
                now - datetime.datetime.strptime(dict['date'], "%Y-%m-%d")).days
            if diff > archivetime:
                n += 1
                v.remove(dict)
    if n == 0:
        summary = None
    else:
        summary = '，' + str(n) + '项已存档'
    print('dateclean: ', summary)
    return (cache, summary)


def alertcheck(alert_page):
    alert_data = load_alertdata()
    data_str = json.dumps(alert_data)
    for data in alert_data:
        if data[1]['alert_page'] == alert_page:
            alert_template = pywikibot.Page(site, u"Template:ArticleAlertbot")
            templates_Params = pywikibot.Page(
                site, alert_page).templatesWithParams()
            for Params_tuple in templates_Params:
                # Params_tuple:  (Page('Template:ArticleAlertbotSubscription'), ['sub=條目狀態通告'])
                if Params_tuple[0] == alert_template:
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
                            workflows = Params[10:].replace(' ', '').lower()
                            workflows_list = workflows.split(',')
                            if 'all' in workflows_list:
                                workflows_list = ['all']
                            if workflows_list != data[1]['workflows']:
                                data[1]['workflows'] = workflows_list
    if data_str != json.dumps(alert_data):
        print('UPDATE: ', alert_data)
        with open('./alert_data/alert_data.json', 'w') as f:
            json.dump(alert_data, f)


def post2wiki(alert_page, workflows, cache, summary):
    text_head = '\n'
    text = ''
    text_foot = '\n'
    alert_input = {}

    for kk, vv in alert_config.alert_types.items():
        alert_input[kk] = ''
        for k, v in cache.items():
            if k in vv:
                if k.lower() in workflows or workflows[0] == 'all':
                    for item in v:
                        alert_input[kk] += item['wikitext']+'\n'
                else:
                    print('workflows参数没有使用规定值')
    for s, c in alert_input.items():
        if c:
            text += '\n;'+s+'\n'+c
    print(summary)
    if text:
        wikipage = pywikibot.Page(site, alert_page)
        wikitext = wikipage.text
        try:
            text_head = re.search(r'(?P<head><noinclude>.*?\{\{ArticleAlertbot\|.*?\}\}.*?</noinclude>)',
                                  wikitext, re.S).group('head') + text_head
        except AttributeError as e:
            print(e)
            print('text_head格式不对')
        try:
            text_foot += re.search(
                r'(?P<foot><noinclude>\{\{ArticleAlertbot\/foot\}\}.*?</noinclude>)', wikitext, re.S).group('foot')
        except AttributeError as e:
            print(e)
            print('text_foot格式不对或不存在')
            text_foot += '<noinclude>{{ArticleAlertbot/foot}}</noinclude>'
    else:
        print('text没有数据')
        text = '目前没有新的条目状态通告。'
    text = text_head + text + text_foot
    # print(text)
    # TEST: 正式测试运行
    wikipage.text = text
    wikipage.save(summary)


# 存档内容处理，提取章节标题和内容
def extract_sections(site, title, sections_pattern):
    page = pywikibot.Page(site, title)
    wikitext = page.text
    result = textlib.extract_sections(wikitext, site)

    for s in result.sections:
        math_section_title = sections_pattern.search(s.title)
        if math_section_title:
            section_title = math_section_title.group(1)
            section_content = s.content
        else:
            section_title = ''
            section_content = ''
    return (section_title, section_content)


# 删除投票讨论中的最后总结部分
def remove_vote_result(content):
    section_content_list = []
    if '----' in content:
        section_content_list = content.split('----')
    elif '<hr>' in content:
        section_content_list = content.split('<hr>')
    if len(section_content_list) > 1:
        section_content_list.pop()
        vote_content = ''.join(section_content_list)
    else:
        vote_content = content
    return vote_content


# 获取在对话页存档的DYK投票讨论内容
def DYK_archive_content(site, talk_title):
    page = pywikibot.Page(site, talk_title)
    wikitext = page.text
    pattern = re.compile(r'{{DYKEntry\/archive.*?{{DYKvoteF}}', re.S)
    DYK_archive_list = pattern.findall(wikitext)
    if DYK_archive_list:
        return DYK_archive_list.pop()
    else:
        return None


# 对结果进行统计
# vote_type is dict：{'支持':['{{全部小写的模板}}'], '反对':['{{全部小写的模板}}']}
def vote_count(site, vote_content, vote_type):
    vote_count = {}
    # 初始化 vote_count = {'支持':0, '反对':0}
    for k in vote_type:
        if k != 'KEEP_ITEMS':
            vote_count[k] = 0
    # 按行拆分
    vote_content = remove_vote_result(vote_content)
    for line in vote_content.lower().splitlines(True):
        for k, v in vote_type.items():
            if k != 'KEEP_ITEMS':
                for t in v:
                    if line.find(t) != -1:
                        vote_count[k] += 1
    stat_list = []
    for k, v in vote_count.items():
        if k in vote_type['KEEP_ITEMS'] or v > 0:
            stat_list.append('%s：%s' % (k, v))
    stat_text = '，'.join(stat_list)
    userscount = users_count(site, vote_content)
    stat_text = '<small>（<abbr title="%s">参与人数：<b>%d</b></abbr>）</small>' % (stat_text, userscount)
    print(stat_text)
    return stat_text


# 提取VFD讨论的内容
def extract_VFD_content(site, vfd_page_title, sections_pattern):
    page = pywikibot.Page(site, vfd_page_title)
    wikitext = page.text
    result = textlib.extract_sections(wikitext, site)
    section_content = ''
    for s in result.sections:
        math_section_title = sections_pattern.search(s.title)
        if math_section_title:
            section_content = s.content
    return section_content


# 讨论人数统计
def users_count(site, vote_content):
    pattern = re.compile(r'\[\[(.*?)\]\]', re.S)
    wikilink_titles = pattern.findall(vote_content)
    users = []
    for title in wikilink_titles:
        if title:
            if title[0] == ':':
                title = title[1:]
            if '|' in title:
                title = title.split('|', 1)[0]
            if pywikibot.Page(site, title).namespace() == 'User:' and title not in users and '/' not in title:  #去除子页面
                users.append(title)
    return len(users)


# 对分类改变的数据进行处理

def process_catdata(site, stream_data, alert_type, wikitextformat, summary='', templates=None, subtype=None, with_talk=False):
    # 解析分类中数据
    title = stream_data['title']
    talk = talkpage(site, title)
    # print(talk)
    if talk.exists() and not talk.isRedirectPage():
        # 从对话页获取WPJ模板
        wpjdata = WPJcheck(site, title)
        if wpjdata:

            print(wpjdata)
            for wpj in wpjdata:
                stream_data['type'] = subtype
                if templates:
                    for tuple in pywikibot.Page(site, title).templatesWithParams():
                        if tuple[0].title() in templates:
                            stream_data['reason'] = '，'.join(
                                list(map(lambda str: str[str.find('=')+1:], tuple[1])))
                if pywikibot.Page(site, title).isTalkPage() and with_talk:
                    stream_data['title'] = pywikibot.Page(
                        site, title).toggleTalkPage().title()
                stream_data['wikitext'] = wikitextformat.format(**stream_data)
                alert_page = wpj[1]['alert_page']
                workflows = wpj[1]['workflows']
                archivetime = wpj[1]['archivetime']
                jsonfile = wpj[1]['jsonfile']
                cache = load_cache('./alert_data/'+jsonfile)
                try:
                    cache_type = cache[alert_type]
                except KeyError:
                    cache[alert_type] = []
                    cache_type = cache[alert_type]

                if cache_type:
                    cache_copy = cache_type.copy()
                    n = 0
                    for i in range(len(cache_copy)):
                        if cache_type[i]['title'] == stream_data['title']:
                            if 'talkat' in cache_type[i]:
                                stream_data['talkat'] = cache_type[i]['talkat']
                                if stream_data['talkat']:
                                    stream_data['wikitext'] = wikitextformat.format(
                                        **stream_data)
                            cache_type[i] = stream_data
                        else:
                            n += 1
                    if len(cache_copy) == n:
                        cache_type.insert(0, stream_data)
                else:
                    cache_type.insert(0, stream_data)
                dateclean_cache = dateclean(cache, archivetime)
                cache = dateclean_cache[0]
                archive_summary = dateclean_cache[1]
                if archive_summary:
                    summary1 = summary + archive_summary  # [[Special:diff/68430264]]
                else:
                    summary1 = summary
                print(stream_data)
                print('Dump: ', jsonfile)
                dump_cache('./alert_data/'+jsonfile, cache)
                alertcheck(alert_page)  # 每次更新时检查alert模板的参数有无变化
                post2wiki(alert_page, workflows, cache, summary1)

# 对分类改变的处理，弃用


def changecat(site, change, alert_type, subtype=None):
    add_matchObj = re.match(alert_config.changecat['add'], change['comment'])
    remove_matchObj = re.match(
        alert_config.changecat['remove'], change['comment'])
    # 加入分类
    if add_matchObj:
        process_catdata(site, add_matchObj, change, alert_type, subtype)
    # 移除分类
    elif remove_matchObj:
        process_catdata(site, remove_matchObj, change, alert_type, subtype)
    else:
        print('Cannot match the comment text in categorize: %s' %
              change['comment'])


# ==========================MAIN=============================
stream = EventStreams(streams=['recentchange'])
stream.register_filter(wiki='zhwiki', type=('categorize', 'log'))
while True:
    change = next(iter(stream))
    # 根据分类改变来识别的alert
    if change['type'] == 'categorize':

        # ================alert页面=======================
        if change['title'] == alert_config.alertcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                alert_data = load_alertdata()
                alert_template = pywikibot.Page(
                    site, u"Template:ArticleAlertbot")
                templates_Params = pywikibot.Page(
                    site, add_matchObj.group(1)).templatesWithParams()
                for Params_tuple in templates_Params:
                    # Params_tuple:  (Page('Template:ArticleAlertbotSubscription'), ['sub=條目狀態通告'])
                    if Params_tuple[0] == alert_template:
                        params_data = {}
                        banner = ''
                        archivetime = 30
                        workflows_list = ['all']
                        for Params in Params_tuple[1]:

                            if Params[:7] == 'banner=' and len(Params) > 7:
                                banner = 'Template:' + Params[7:]

                            elif Params[:12] == 'archivetime=' and len(Params) > 12 and Params[12:].isdigit():
                                archivetime = int(Params[12:])
                            elif Params[:10] == 'workflows=' and len(Params) > 10:
                                workflows = Params[10:].replace(
                                    ' ', '').lower()
                                workflows_list = workflows.split(',')
                                if 'all' in workflows_list:
                                    workflows_list = ['all']

                        if banner and pywikibot.Page(site, banner).exists():
                            params_data['alert_page'] = add_matchObj.group(1)
                            params_data['archivetime'] = archivetime
                            params_data['workflows'] = workflows_list
                            params_data['jsonfile'] = add_matchObj.group(
                                1).replace('/', '_')+'.json'
                            alert_data.append((banner, params_data))
                            with open('./alert_data/alert_data.json', 'w') as f:
                                json.dump(alert_data, f)
                print(change)
                print(alert_data)

            # 移除分类
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
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================CSD=======================
        if change['title'] == alert_config.csdcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="{reason}">速删</abbr>'
                summary = '速删：+[[' + add_matchObj.group(1) + ']]'
                process_catdata(site, categorize(add_matchObj, change), 'CSD',
                                wikitextformat, summary, templates=['Template:Delete'])
            # 移除分类
            elif remove_matchObj:
                summary = '速删：-[[' + remove_matchObj.group(1) + ']]'
                # stream_data = categorize(remove_matchObj, change)
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(
                        site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}|small=1}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isCategoryRedirect():
                    target = pywikibot.Page(site, remove_matchObj.group(
                        1)).getCategoryRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}|small=1}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}|small=1}}}}改为消歧义页'
                else:
                    wikitextformat = '* {date}：[[:{title}]]提交速删后被{{{{User|{user}|small=1}}}}保留'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'CSD', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])
            # TODO：{{hang on|理由}}，现缺少专门分类

        # ================NOZH=======================
        if change['title'] == alert_config.nozhcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                wikitextformat = '* {date}：[[:{title}]]需要翻译'
                summary = '翻译：+[[' + add_matchObj.group(1) + ']]'
                process_catdata(site, categorize(add_matchObj, change), 'CSD',
                                wikitextformat, summary)

        # ================NOZH > 2 week=======================
        if change['title'] == alert_config.nozh2cat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                wikitextformat = '* {date}：[[:{title}]]超过两周没有翻译'
                summary = '翻译：[[' + add_matchObj.group(1) + ']]'
                process_catdata(site, categorize(add_matchObj, change), 'CSD',
                                wikitextformat, summary)

        # ================FCSD文件速删(与CSD合并)=======================
        elif change['title'] in alert_config.filecsd_cats:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '文件速删：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="<nowiki>{type}</nowiki>">速删</abbr>'
                process_catdata(site, categorize(add_matchObj, change), 'CSD',
                                wikitextformat, summary, subtype=change['title'].split(':', 1)[1])
            # 移除分类
            elif remove_matchObj:
                summary = '文件速删：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交<abbr title="<nowiki>{type}</nowiki>">速删</abbr>后被{{{{User|{user}|small=1}}}}保留'
                process_catdata(site, categorize(remove_matchObj, change), 'CSD',
                                wikitextformat, summary, subtype=change['title'].split(':', 1)[1])
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================VFD=======================
        elif change['title'] in alert_config.vfdcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '存废：+[[' + add_matchObj.group(1) + ']]'
                vfdtemplate = ['Template:Vfd', 'Template:Afd', 'Template:Cfd',
                               'Template:Tfd', 'Template:Ufd', 'Template:Mfd', 'Template:Rfd']
                templates_Params = pywikibot.Page(
                    site, add_matchObj.group(1)).templatesWithParams()
                vfddate = ''
                for Params_tuple in templates_Params:
                    if Params_tuple[0].title() in vfdtemplate:
                        for p in Params_tuple[1]:
                            if p.split('=', 1)[0].lower() == 'date':
                                vfddate = p.split('=', 1)[1]
                if vfddate:
                    vfd_file = './alert_data/vfddata.json'
                    try:
                        with open(vfd_file, 'r') as f:
                            vfddata = json.load(f)
                    except FileNotFoundError:
                        vfddata = {}
                    vfd_title = add_matchObj.group(1)
                    vfd_page_title = 'Wikipedia:頁面存廢討論/記錄/%s' % vfddate
                    vfddata[vfd_title] = vfd_page_title
                    dump_cache(vfd_file, vfddata)

                    talkat = '➡️ [[Wikipedia:頁面存廢討論/記錄/%s#%s|讨论存档]]' % (
                        vfddate, add_matchObj.group(1))
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="<nowiki>{reason}</nowiki>">存废讨论</abbr> ➡️ [[Wikipedia:頁面存廢討論/記錄/%s#%s|参与讨论]]' % (
                        vfddate, add_matchObj.group(1))
                else:
                    talkat = ''
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="<nowiki>{reason}</nowiki>">存废讨论</abbr>'
                process_catdata(site, categorize(add_matchObj, change, talkat=talkat),
                                'VFD', wikitextformat, summary, vfdtemplate)
            # 移除分类
            elif remove_matchObj:
                summary = '存废：-[[' + remove_matchObj.group(1) + ']]'
                vfd_title = remove_matchObj.group(1)
                sections_pattern = re.compile(
                    r'==+ *\[\[:(%s)\]\] *==+' % re.escape(vfd_title))
                vote_type = {'保留': ['{{保留}}', '{{keep}}', '{{vk}}', '{{已打捞}}', '{{已打撈}}', '{{saved}}', '{{salvaged}}', '{{已}}', '{{快速保留}}', '{{sk}}', '{{speedy keep}}', '{{快保}}', '{{vtk}}', '{{暫時保留}}', '{{暂时保留}}'],
                             '删除': ['{{vd}}', '{{删除}}', '{{刪除}}', '{{del}}', '{{removal}}', '{{remove}}', '{{vsd}}', '{{快速刪除}}', '{{vn}}', '{{删后重建}}', '{{刪後重建}}', '{{vtn}}', '{{到時重建}}'],
                             '中立': ['{{neutral}}', '{{中立}}'],
                             '消歧义': ['{{vdab}}', '{{改為消歧義}}'],
                             '重定向': ['{{vr}}', '{{重定向}}', '{{重新導向}}'],
                             '移動': ['{{nvm}}', '{{不留重定向移動}}', '{{不留重新導向移動}}', '{{vmp}}', '{{vmove}}', '{{移動}}', '{{移动}}', '{{迁移}}', '{{转移}}', '{{move to}}', '{{userfy}}', '{{移动到用户页}}', '{{vmu}}', '{{移動到用戶頁}}', '{{移動至用戶頁}}', '{{迁移到用户页}}', '{{移動到使用者頁面}}'],
                             '合并': ['{{vm}}', '{{合并}}', '{{合併}}', '{{vmerge}}'],
                             '迁移到其他计划': ['{{vmd}}', '{{移動到詞典}}', '{{移动到词典}}', '{{vmt}}', '{{移動到辭典}}', '{{迁移到词典}}', '{{vms}}', '{{移動到文庫}}', '{{移动到文库}}', '{{迁移到文库}}', '{{vmb}}', '{{移動到教科書}}', '{{移动到教科书}}', '{{迁移到教科书}}', '{{vmq}}', '{{移動到語錄}}', '{{移动到语录}}', '{{迁移到语录}}', '{{vmvoy}}', '{{迁移到导游}}', '{{移动到导游}}', '{{移動到導遊}}', '{{vmv}}', '{{迁移到学院}}', '{{移動到學院}}'],
                             '意见': ['{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'],
                             'KEEP_ITEMS': ['保留', '删除']
                             }
                vfd_file = './alert_data/vfddata.json'
                try:
                    with open(vfd_file, 'r') as f:
                        vfddata = json.load(f)
                except FileNotFoundError:
                    vfddata = {}
                if vfd_title in vfddata:
                    vote_content = extract_VFD_content(
                        site, vfddata[vfd_title], sections_pattern)
                    stat_text = vote_count(site, vote_content, vote_type)
                else:
                    stat_text = ''

                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(
                        site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}|small=1}}}}重定向到[[:%s]] {talkat} %s' % (
                        target.title(), stat_text)
                elif pywikibot.Page(site, remove_matchObj.group(1)).isCategoryRedirect():
                    target = pywikibot.Page(site, remove_matchObj.group(
                        1)).getCategoryRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}|small=1}}}}重定向到[[:%s]] {talkat} %s' % (
                        target.title(), stat_text)
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}|small=1}}}}改为消歧义页 {talkat} %s' % stat_text
                else:
                    wikitextformat = '* {date}：[[:{title}]]提交存废讨论后被{{{{User|{user}|small=1}}}}保留 {talkat} %s' % stat_text
                process_catdata(site, categorize(
                    remove_matchObj, change), 'VFD', wikitextformat, summary)
                try:
                    del vfddata[vfd_title]
                except KeyError as e:
                    print('KeyError: ', e)

                dump_cache(vfd_file, vfddata)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================IFD（与VFD合并）=======================
        # TODO: 计票
        elif change['title'] == alert_config.ifdcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '文件删除：+[[' + add_matchObj.group(1) + ']]'
                ifdtemplate = 'Template:Ifd'
                templates_Params = pywikibot.Page(
                    site, add_matchObj.group(1)).templatesWithParams()
                ifddate = ''
                for Params_tuple in templates_Params:
                    if Params_tuple[0].title() == ifdtemplate:
                        for p in Params_tuple[1]:
                            if p.split('=', 1)[0].lower() == 'date':
                                ifddate = p.split('=', 1)[1]
                if ifddate:
                    talkat = '➡️ [[Wikipedia:檔案存廢討論/記錄/%s#%s|讨论存档]]' % (
                        ifddate, add_matchObj.group(1))
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="<nowiki>{reason}</nowiki>">文件删除讨论</abbr> ➡️ [[Wikipedia:檔案存廢討論/記錄/%s#%s|参与讨论]]' % (
                        ifddate, add_matchObj.group(1))
                else:
                    talkat = ''
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交<abbr title="<nowiki>{reason}</nowiki>">文件删除讨论</abbr>'
                process_catdata(site, categorize(add_matchObj, change, talkat=talkat),
                                'VFD', wikitextformat, summary, ['Template:Ifd'])
            # 移除分类
            elif remove_matchObj:
                summary = '文件删除：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交文件删除讨论后被{{{{User|{user}|small=1}}}}保留 {talkat}'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'VFD', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================Transwiki=======================
        # TODO: 讨论位置，计票
        elif change['title'] in alert_config.transwikicat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '移动到其他计划：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议{type}'
                process_catdata(site, categorize(add_matchObj, change), 'TRANS',
                                wikitextformat, summary, subtype=change['title'].split(':', 1)[1])
            # 移除分类
            elif remove_matchObj:
                summary = '移动到其他计划：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]建议{type}后被{{{{User|{user}|small=1}}}}保留'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'TRANS', wikitextformat, summary, subtype=change['title'].split(':', 1)[1])
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================COPYVIO=======================
        elif change['title'] == alert_config.copyviocat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '侵权：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}怀疑侵权'
                process_catdata(site, categorize(
                    add_matchObj, change), 'COPYVIO', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '侵权：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}解决了侵权问题'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'COPYVIO', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================重写COPYVIO=======================
        elif change['title'] == alert_config.rewritecpcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                alert_data = load_cache('./alert_data/alert_data.json')
                for data in alert_data:
                    file = data[1]['jsonfile']
                    alert_page = data[1]['alert_page']
                    workflows = data[1]['workflows']
                    archivetime = data[1]['archivetime']
                    cache = load_cache('./alert_data/'+file)
                    cachestr = json.dumps(cache)

                    for k, v in cache.items():
                        if k == 'COPYVIO':
                            i = 0
                            for dict in v:
                                try:
                                    rwtitle = add_matchObj.group(
                                        1).split(':', 1)[1]
                                except IndexError:
                                    rwtitle = add_matchObj.group(1)
                                if dict['title'] == rwtitle:
                                    summary = '侵权重写：[[' + \
                                        add_matchObj.group(1) + ']]'
                                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}）重写于[[%s]]' % add_matchObj.group(
                                        1)
                                    stream_data = categorize(
                                        add_matchObj, change)
                                    stream_data['wikitext'] = wikitextformat.format(
                                        **stream_data)
                                    v[i] = stream_data
                                i += 1
                    if cachestr != json.dumps(cache):
                        dateclean_cache = dateclean(cache, archivetime)
                        cache = dateclean_cache[0]
                        archive_summary = dateclean_cache[1]
                        if archive_summary:
                            summary1 = summary + archive_summary  # [[Special:diff/68430264]]
                        else:
                            summary1 = summary
                        print(stream_data)
                        # print(change)
                        print('Dump: ', jsonfile)
                        dump_cache('./alert_data/'+file, cache)
                        alertcheck(alert_page)
                        post2wiki(alert_page, workflows, cache, summary1)

            # TODO: 移除分类是否要处理?

        # ================DRV存废复核=======================
        elif change['title'] == alert_config.drvcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '存废复核：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提交[[Wikipedia:存廢覆核請求#{title}|存废复核]]'
                process_catdata(site, categorize(
                    add_matchObj, change), 'DRV', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '存废复核：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]提交存废复核后被{{{{User|{user}|small=1}}}}保留 ➡️ [[Wikipedia:存廢覆核請求#{title}|讨论结果]]'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'DRV', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================DYKC=======================
        elif change['title'] == alert_config.dykccat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'DYK：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:新条目推荐/候选#{title}|新条目推荐候选]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'DYK', wikitextformat, summary, with_talk=True)

        # ================DYK=======================
        elif change['title'] == alert_config.dykcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'DYK：+[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                archive_content = DYK_archive_content(
                    site, add_matchObj.group(1))
                if archive_content:
                    vote_type = {'支持': ['{{support}}', '{{支持}}', '{{pro}}', '{{sp}}', '{{zc}}'], '反对': [
                        '{{oppose}}', '{{反对}}', '{{反對}}', '{{contra}}', '{{不同意}}', '{{o}}'], 'KEEP_ITEMS': ['支持', '反对']}
                    stat_text = vote_count(site, archive_content, vote_type)
                    wikitextformat = '* {date}：[[:{title}]]已通过新条目推荐 ➡️ [[Talk:{title}#新条目推荐讨论|讨论存档]] %s' % stat_text
                else:
                    wikitextformat = '* {date}：[[:{title}]]已通过新条目推荐 ➡️ [[Talk:{title}#新条目推荐讨论|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'DYK', wikitextformat, summary, with_talk=True)

        # ================FLC,FLR重选,FLK重选维持=======================
        elif change['title'] == alert_config.flccat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            """remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])"""
            if add_matchObj:
                summary = 'FL：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:Featured list removal candidates') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:特色列表评选#{title}|重选特色列表]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:特色列表评选#{title}|评选特色列表]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)
            """elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:Featured list') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'FL：[[' + \
                        remove_matchObj.group(1).split(':', 1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了特色列表状态 ➡️ [[Talk:{title}|讨论存档]]'
                    process_catdata(site, categorize(
                        remove_matchObj, change), 'FC', wikitextformat, summary, with_talk=True)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])"""

        # ================FL=======================
        elif change['title'] == alert_config.flcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                sections_pattern = re.compile(
                    r'==+ *(.*?特色列表[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfl}}'], '反对': ['{{nofl}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:特色列表|特色列表]] ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:特色列表|特色列表]] ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:特色列表|特色列表]] ➡️ [[Talk:{title}|讨论存档]]'
                summary = 'FL：+[[' + add_matchObj.group(1) + ']]'
                process_catdata(site, categorize(
                    add_matchObj, change), 'FC', wikitextformat, summary, with_talk=True)

        # ================FLFailed落选=======================
        elif change['title'] == alert_config.flfcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'FL：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?特色列表[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfl}}'], '反对': ['{{nofl}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]评选特色列表失败 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]评选特色列表失败 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]评选特色列表失败 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)

        # ================FFL撤销=======================
        elif change['title'] == alert_config.fflcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'FL：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(r'==+ *(.*?特色列表重[审|審].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfl}}'], '反对': ['{{nofl}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已撤销特色列表状态 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已撤销特色列表状态 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已撤销特色列表状态 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)

        # ================FAC，FAR，FAK=======================
        elif change['title'] == alert_config.faccat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            """remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])"""
            if add_matchObj:
                summary = 'FA：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:Featured article review') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:典范条目评选#{title}|重选典范条目]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:典范条目评选#{title}|评选典范条目]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)
            """elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:Featured article') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'FA：+[[' + \
                        remove_matchObj.group(1).split(':', 1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了典范条目状态 ➡️ [[Talk:{title}|讨论存档]]'
                    process_catdata(site, categorize(
                        remove_matchObj, change), 'FC', wikitextformat, summary, with_talk=True)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])"""

        # ================FA=======================
        elif change['title'] == alert_config.facat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'FA：+[[' + add_matchObj.group(1) + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?典[范|範][條|条]目[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfa}}'], '反对': ['{{nofa}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:典范条目|典范条目]] ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:典范条目|典范条目]] ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:典范条目|典范条目]] ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(
                    add_matchObj, change), 'FC', wikitextformat, summary, with_talk=True)

        # ================FAF落选=======================
        elif change['title'] == alert_config.fafcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'FA：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?典[范|範][條|条]目[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfa}}'], '反对': ['{{nofa}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]评选典范条目失败 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]评选典范条目失败 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]评选典范条目失败 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)

        # ================FAL撤销=======================
        elif change['title'] == alert_config.falcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'FA：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?典[范|範][條|条]目重[审|審].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesfa}}'], '反对': ['{{nofa}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已撤销典范条目状态 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已撤销典范条目状态 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已撤销典范条目状态 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'FC', wikitextformat, summary, with_talk=True)

        # ================GAN,GAR,GAK=======================
        elif change['title'] == alert_config.gancat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            """remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])"""
            if add_matchObj:
                summary = 'GA：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                if pywikibot.Page(site, add_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:GA reassessment') in pywikibot.Page(site, add_matchObj.group(1)).templates():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:優良條目評選#{title}|重选优良条目]]'
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:優良條目評選#{title}|评选优良条目]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'GA', wikitextformat, summary, with_talk=True)
            """elif remove_matchObj:
                if pywikibot.Page(site, remove_matchObj.group(1)).isTalkPage() and pywikibot.Page(site, 'Template:Good article') in pywikibot.Page(site, remove_matchObj.group(1)).toggleTalkPage().templates():
                    summary = 'GA：+[[' + \
                        remove_matchObj.group(1).split(':', 1)[1] + ']]'
                    wikitextformat = '* {date}：[[:{title}]]重选后维持了優良条目状态 -> [[Talk:{title}|讨论存档]]'
                    process_catdata(site, categorize(
                        remove_matchObj, change), 'GA', wikitextformat, summary, with_talk=True)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])"""

        # ================GA=======================
        elif change['title'] == alert_config.gacat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                sections_pattern = re.compile(
                    r'==+ *(.*?[優|优]良[條|条]目[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                summary = 'GA：+[[' + add_matchObj.group(1).split(':', 1)[1] + ']]'
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesga}}'], '反对': ['{{noga}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:優良条目|優良条目]] ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:優良条目|優良条目]] ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已被评为[[Wikipedia:優良条目|優良条目]] ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(
                    add_matchObj, change), 'GA', wikitextformat, summary, with_talk=True)

        # ================GAF落选=======================
        elif change['title'] == alert_config.gafcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'GA：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?[優|优]良[條|条]目[評|评][選|选].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesga}}'], '反对': ['{{noga}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]评选優良条目失败 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]评选優良条目失败 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]评选優良条目失败 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'GA', wikitextformat, summary, with_talk=True)

        # ================GAL撤销=======================
        elif change['title'] == alert_config.galcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'GA：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?[優|优]良[條|条]目重[审|審].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    if section[1]:
                        vote_type = {'支持': ['{{yesga}}'], '反对': ['{{noga}}'], '中立': ['{{neutral}}', '{{中立}}'], '意见': [
                            '{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'], 'KEEP_ITEMS': ['支持', '反对']}
                        stat_text = vote_count(site, section[1], vote_type)
                        wikitextformat = '* {date}：[[:{title}]]已撤销优良条目状态 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (
                            section[0], stat_text)
                    else:
                        wikitextformat = '* {date}：[[:{title}]]已撤销优良条目状态 ➡️ [[Talk:{title}#%s|讨论存档]]' % section[0]
                else:
                    wikitextformat = '* {date}：[[:{title}]]已撤销优良条目状态 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'GA', wikitextformat, summary, with_talk=True)

        # ================PR=======================
        elif change['title'] == alert_config.prcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'PR：+[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}提名[[Wikipedia:同行评审#{title}|同行评审]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'PR', wikitextformat, summary, with_talk=True)

        # ================PR结束=======================
        elif change['title'] == alert_config.predcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = 'PR：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                sections_pattern = re.compile(
                    r'==+ *(.*?同行[評|评][審|审].*?) *==+')
                section = extract_sections(
                    site, add_matchObj.group(1), sections_pattern)
                if section[0]:
                    stat_text = '<small>（参与人数：<b>%d</b>）</small>' % users_count(site, remove_vote_result(section[1]))
                    wikitextformat = '* {date}：[[:{title}]]已结束同行评审 ➡️ [[Talk:{title}#%s|讨论存档]] %s' % (section[0], stat_text)
                else:
                    wikitextformat = '* {date}：[[:{title}]]已结束同行评审 ➡️ [[Talk:{title}|讨论存档]]'
                process_catdata(site, categorize(add_matchObj, change),
                                'PR', wikitextformat, summary, with_talk=True)

        # ================拆分=======================
        # TODO: 拆分成哪些页面
        elif change['title'] == alert_config.splitcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '拆分：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议拆分'
                process_catdata(site, categorize(
                    add_matchObj, change), 'SPLIT', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '拆分：-[[' + remove_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]已经由{{{{User|{user}|small=1}}}}解决了拆分问题'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'SPLIT', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================小小作品=======================
        elif change['title'] in alert_config.substubcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '小小作品：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}标记为小小作品'
                process_catdata(site, categorize(
                    add_matchObj, change), 'SUB', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '小小作品：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(
                        site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}改为消歧义页'
                else:
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}移除了小小作品标记'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'SUB', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================关注度=======================
        elif change['title'] in alert_config.notabilitycat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '关注度：+[[' + add_matchObj.group(1) + ']]'
                wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}认为缺乏关注度'
                process_catdata(site, categorize(
                    add_matchObj, change), 'FAME', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '关注度：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(
                        site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}重定向到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}改为消歧义页'
                else:
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}移除了关注度标记'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'FAME', wikitextformat, summary)
            else:
                print('Cannot match the comment text in categorize: %s' %
                      change['comment'])

        # ================MV移动请求=======================
        elif change['title'] == alert_config.rmvcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = '移动请求：+[[' + add_matchObj.group(1) + ']]'
                for tuple in pywikibot.Page(site, add_matchObj.group(1)).templatesWithParams():
                    if tuple[0].title() == 'Template:Requested move':
                        if tuple[1]:
                            for t in tuple[1]:
                                if '=' not in t:
                                    moveto = t
                                    wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}请求移动到[[%s]]' % t
                        else:
                            moveto = ''
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}请求移动到新名称'
                        process_catdata(site,  categorize(
                            add_matchObj, change, moveto=moveto), 'MV', wikitextformat, summary)

        elif change['title'] == alert_config.rmcdonecat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = '移动请求：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已完成了移动请求 ➡️ [[%s|讨论存档]]' % add_matchObj.group(
                    1)
                process_catdata(site,  categorize(
                    add_matchObj, change), 'MV', wikitextformat, summary, with_talk=True)

        elif change['title'] == alert_config.rmcndcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = '移动请求：-[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]的移动请求已被拒绝 ➡️ [[%s|讨论存档]]' % add_matchObj.group(
                    1)
                process_catdata(site,  categorize(
                    add_matchObj, change), 'MV', wikitextformat, summary, with_talk=True)

        elif change['title'] == alert_config.rmcnmcat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = '移动请求：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]的移动请求已讨论通过，等待处理 ➡️ [[%s|讨论存档]]' % add_matchObj.group(
                    1)
                process_catdata(site,  categorize(
                    add_matchObj, change), 'MV', wikitextformat, summary, with_talk=True)

        elif change['title'] == alert_config.rmccat:
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            if add_matchObj:
                summary = '移动请求：[[' + \
                    add_matchObj.group(1).split(':', 1)[1] + ']]'
                wikitextformat = '* {date}：[[:{title}]]的移动请求[[%s|正在讨论]]' % add_matchObj.group(
                    1)
                process_catdata(site,  categorize(
                    add_matchObj, change), 'MV', wikitextformat, summary, with_talk=True)

        # ================MM合并=======================
        # TODO: [[Template:Merge approved]]的处理？
        elif change['title'] in alert_config.mmcat or re.search(alert_config.mmrecat, change['title']):
            add_matchObj = re.match(
                alert_config.changecat['add'], change['comment'])
            remove_matchObj = re.match(
                alert_config.changecat['remove'], change['comment'])
            if add_matchObj:
                summary = '合并：+[[' + add_matchObj.group(1) + ']]'
                for tuple in pywikibot.Page(site, add_matchObj.group(1)).templatesWithParams():
                    mmitem = []
                    if tuple[0].title() == 'Template:Merge from':
                        if tuple[1]:
                            for t in tuple[1]:
                                if '=' not in t:
                                    mmitem.append(t)
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                        if mmitem:
                            mmstr = ']]、[['.join(mmitem)
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议将[[%s]]合并到本页' % mmstr
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                    elif tuple[0].title() == 'Template:Merge to':
                        if tuple[1]:
                            for t in tuple[1]:
                                if '=' not in t:
                                    mmitem.append(t)
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                        if mmitem:
                            mmstr = ']]、[['.join(mmitem)
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并到[[%s]]' % mmstr
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                    elif tuple[0].title() == 'Template:Merge':
                        if tuple[1]:
                            for t in tuple[1]:
                                if '=' not in t:
                                    mmitem.append(t)
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                        if mmitem:
                            mmstr = ']]、[['.join(mmitem)
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议与[[%s]]合并' % mmstr
                        else:
                            wikitextformat = '* {date}：[[:{title}]]被{{{{User|{user}|small=1}}}}建议合并'
                    elif tuple[0].title() == 'Template:Merging':
                        if tuple[1]:
                            for t in tuple[1]:
                                if '=' not in t:
                                    mmitem.append(t)
                        else:
                            wikitextformat = '* {date}：[[:{title}]]正在被{{{{User|{user}|small=1}}}}计划合并'
                        if mmitem:
                            mmstr = ']]、[['.join(mmitem)
                            wikitextformat = '* {date}：[[:{title}]]正在被{{{{User|{user}|small=1}}}}计划与[[%s]]合并' % mmstr
                        else:
                            wikitextformat = '* {date}：[[:{title}]]正在被{{{{User|{user}|small=1}}}}计划合并'
                process_catdata(site, categorize(
                    add_matchObj, change), 'MM', wikitextformat, summary)
            # 移除分类
            elif remove_matchObj:
                summary = '合并：-[[' + remove_matchObj.group(1) + ']]'
                if pywikibot.Page(site, remove_matchObj.group(1)).isRedirectPage():
                    target = pywikibot.Page(
                        site, remove_matchObj.group(1)).getRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}合并到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isCategoryRedirect():
                    target = pywikibot.Page(site, remove_matchObj.group(
                        1)).getCategoryRedirectTarget()
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}合并到[[:%s]]' % target.title()
                elif pywikibot.Page(site, remove_matchObj.group(1)).isDisambig():
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}合并后改为消歧义页'
                elif not pywikibot.Page(site, remove_matchObj.group(1)).exists():
                    wikitextformat = '* {date}：[[:{title}]]在解决了合并问题后被删除'
                else:
                    wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}解决了合并问题'
                process_catdata(site, categorize(
                    remove_matchObj, change), 'MM', wikitextformat, summary)

    # log操作
    if change['type'] == 'log':
        # ================删除相关=======================
        if change['log_type'] == 'delete' and change['log_action'] == 'delete':
            path = './alert_data/'
            alert_data = load_cache('./alert_data/alert_data.json')
            for data in alert_data:
                file = data[1]['jsonfile']
                alert_page = data[1]['alert_page']
                workflows = data[1]['workflows']
                archivetime = data[1]['archivetime']
                cache = load_cache('./alert_data/'+file)
                cachestr = json.dumps(cache)

                for k, v in cache.items():
                    i = 0
                    for dict in v:
                        if dict['title'] == change['title']:
                            summary = '-[[' + change['title'] + ']]已删除'
                            wikitextformat = '* {{{{color|#72777d|{date}}}}}：[[:{title}]]已被{{{{User|{user}|small=1}}}}<abbr title="<nowiki>{reason}</nowiki>">删除</abbr> <small>（{{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}）</small> {talkat}'
                            stream_data = logdata(change)
                            if 'talkat' in dict:
                                #stream_data['talkat'] = dict['talkat']
                                #vfdlink_pattern = re.compile(r'\[\[(Wikipedia:頁面存廢討論/記錄/.*?)#.*?')
                                #vfd_math = vfdlink_pattern.saerch(dict['talkat'])
                                #if vfd_math:
                                #    vfd_link = vfd_math.group(1)
                                sections_pattern = re.compile(r'==+ *\[\[:(%s)\]\] *==+' % re.escape(change['title']))
                                vote_type = {'保留': ['{{保留}}', '{{keep}}', '{{vk}}', '{{已打捞}}', '{{已打撈}}', '{{saved}}', '{{salvaged}}', '{{已}}', '{{快速保留}}', '{{sk}}', '{{speedy keep}}', '{{快保}}', '{{vtk}}', '{{暫時保留}}', '{{暂时保留}}'],
                                    '删除': ['{{vd}}', '{{删除}}', '{{刪除}}', '{{del}}', '{{removal}}', '{{remove}}', '{{vsd}}', '{{快速刪除}}', '{{vn}}', '{{删后重建}}', '{{刪後重建}}', '{{vtn}}', '{{到時重建}}'],
                                    '中立': ['{{neutral}}', '{{中立}}'],
                                    '消歧义': ['{{vdab}}', '{{改為消歧義}}'],
                                    '重定向': ['{{vr}}', '{{重定向}}', '{{重新導向}}'],
                                    '移動': ['{{nvm}}', '{{不留重定向移動}}', '{{不留重新導向移動}}', '{{vmp}}', '{{vmove}}', '{{移動}}', '{{移动}}', '{{迁移}}', '{{转移}}', '{{move to}}', '{{userfy}}', '{{移动到用户页}}', '{{vmu}}', '{{移動到用戶頁}}', '{{移動至用戶頁}}', '{{迁移到用户页}}', '{{移動到使用者頁面}}'],
                                    '合并': ['{{vm}}', '{{合并}}', '{{合併}}', '{{vmerge}}'],
                                    '迁移到其他计划': ['{{vmd}}', '{{移動到詞典}}', '{{移动到词典}}', '{{vmt}}', '{{移動到辭典}}', '{{迁移到词典}}', '{{vms}}', '{{移動到文庫}}', '{{移动到文库}}', '{{迁移到文库}}', '{{vmb}}', '{{移動到教科書}}', '{{移动到教科书}}', '{{迁移到教科书}}', '{{vmq}}', '{{移動到語錄}}', '{{移动到语录}}', '{{迁移到语录}}', '{{vmvoy}}', '{{迁移到导游}}', '{{移动到导游}}', '{{移動到導遊}}', '{{vmv}}', '{{迁移到学院}}', '{{移動到學院}}'],
                                    '意见': ['{{意见}}', '{{意見}}', '{{opinion}}', '{{comment}}', '{{cmt}}'],
                                    'KEEP_ITEMS': ['保留', '删除']
                                    }
                                vfd_file = './alert_data/vfddata.json'
                                try:
                                    with open(vfd_file, 'r') as f:
                                        vfddata = json.load(f)
                                except FileNotFoundError:
                                    vfddata = {}
                                if change['title'] in vfddata:
                                    vote_content = extract_VFD_content(
                                        site, vfddata[change['title']], sections_pattern)
                                    stat_text = vote_count(site, vote_content, vote_type)
                                    wikitextformat = '* {{{{color|#72777d|{date}}}}}：[[:{title}]]已被{{{{User|{user}|small=1}}}}<abbr title="<nowiki>{reason}</nowiki>">删除</abbr> <small>（{{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}）</small> {talkat} %s' % stat_text
                                    try:
                                        del vfddata[change['title']]
                                    except KeyError as e:
                                        print('KeyError: ', e)

                                    dump_cache(vfd_file, vfddata)
                            else:
                                stream_data['talkat'] = ''
                            stream_data['wikitext'] = wikitextformat.format(
                                **stream_data)
                            v[i] = stream_data
                        i += 1
                if cachestr != json.dumps(cache):
                    dateclean_cache = dateclean(cache, archivetime)
                    cache = dateclean_cache[0]
                    archive_summary = dateclean_cache[1]
                    if archive_summary:
                        summary1 = summary + archive_summary  # [[Special:diff/68430264]]
                    else:
                        summary1 = summary
                    print(stream_data)
                    # print(change)
                    print('Dump: ', jsonfile)
                    dump_cache('./alert_data/'+file, cache)
                    alertcheck(alert_page)
                    post2wiki(alert_page, workflows, cache, summary1)

        # ================保护=======================
        elif change['log_type'] == 'protect':
            if change['log_action'] == 'protect':
                # TODO:编辑请求
                summary = '保护：+[[' + change['title'] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}<abbr title="<nowiki>{reason}</nowiki>">保护</abbr> <small>（{{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}）</small>'
                process_catdata(site, logdata(change), 'PP',
                                wikitextformat, summary, subtype='protect')
            # 解除保护
            elif change['log_action'] == 'unprotect':
                summary = '解除保护：-[[' + change['title'] + ']]'
                wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}<abbr title="<nowiki>{reason}</nowiki>">解除保护</abbr> <small>（{{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}）</small>'
                process_catdata(site, logdata(change), 'PP',
                                wikitextformat, summary, subtype='unprotect')
        # ================移动=======================
        elif change['log_type'] == 'move':
            alert_data = load_cache('./alert_data/alert_data.json')
            for data in alert_data:
                file = data[1]['jsonfile']
                alert_page = data[1]['alert_page']
                workflows = data[1]['workflows']
                archivetime = data[1]['archivetime']
                cache = load_cache('./alert_data/'+file)
                cachestr = json.dumps(cache)

                for k, v in cache.items():
                    if k == 'MV':
                        i = 0
                        for dict in v:
                            if dict['title'] == change['title']:
                                summary = '移动：-[[' + change['title'] + ']]'
                                wikitextformat = '* {date}：[[:{title}]]已被{{{{User|{user}|small=1}}}}<abbr title="<nowiki>{reason}</nowiki>">移动到</abbr>[[:{moveto}]] <small>（{{{{Plain link|{{{{fullurl:Special:log|logid={id}}}}}|log}}}}）</small>'
                                stream_data = logdata(change)
                                stream_data['wikitext'] = wikitextformat.format(
                                    **stream_data)
                                v[i] = stream_data
                            i += 1
                if cachestr != json.dumps(cache):
                    dateclean_cache = dateclean(cache, archivetime)
                    cache = dateclean_cache[0]
                    archive_summary = dateclean_cache[1]
                    if archive_summary:
                        summary1 = summary + archive_summary  # [[Special:diff/68430264]]
                    else:
                        summary1 = summary
                    print(stream_data)
                    # print(change)
                    print('Dump: ', jsonfile)
                    dump_cache('./alert_data/'+file, cache)
                    alertcheck(alert_page)
                    post2wiki(alert_page, workflows, cache, summary1)


"""TODO: 
3.今日首页（特色，优良，ITN？）
4.新建条目？

"""
"""
{'title': 'Category:移動重定向', 'bot': True, 'server_name': 'zh.wikipedia.org', 'meta': {'partition': 0, 'offset': 3310430515, 'domain': 'zh.wikipedia.org', 'stream': 'mediawiki.recentchange', 'topic': 'eqiad.mediawiki.recentchange', 'id': '8747fb90-de3d-47fd-9a09-5d2bf311532f', 'uri': 'https://zh.wikipedia.org/wiki/Category:%E7%A7%BB%E5%8B%95%E9%87%8D%E5%AE%9A%E5%90%91', 'dt': '2021-09-20T13:10:03Z', 'request_id': '138f3062-477a-4cfc-bcda-4cbd8d844426'}, 'wiki': 'zhwiki', 'parsedcomment': '<a href="/wiki/User:Renbaoshuo" class="mw-redirect" title="User:Renbaoshuo">User:Renbaoshuo</a>已添加至分类', 'server_script_path': '/w', 'user': 'Jimmy Xu', 'namespace': 14, 'timestamp': 1632143403, 'comment': '[[:User:Renbaoshuo]]已添加至分类', 'server_url': 'https://zh.wikipedia.org', '$schema': '/mediawiki/recentchange/1.0.0', 'id': 138715371, 'type': 'categorize'}



User:激鬥峽谷已从分类中移除
"""

"""
[['Template:足球專題', {'alert_page': 'WikiProject:足球/條目狀態', 'jsonfile': 'WikiProject:足球_條目狀態.json', 'workflows': ['all'], 'archivetime': 30}], ['Template:WikiProject Biography', {'alert_page': 'User:Shizhao/test2/1', 'jsonfile': 'User:Shizhao_test2_1.json', 'workflows': ['all'], 'archivetime': 40}]]
{'title': 'User:Shizhao/test3', 'user': 'Shizhao', 'action': '添加', 'date': '2021-09-23'}
"""

"""
{'log_type': 'delete', 'log_action': 'delete', 'log_action_comment': 'deleted &quot;[[舞法天少女朵法拉第七季]]&quot;：[[WP:CSD#G3|G3]]: 纯粹[[WP:VAN|破坏]]，包括但不限于明显的[[WP:HOAX|恶作剧]]、错误信息、[[WP:PA|人身攻击]]等', 'user': 'Shizhao', 'id': 138940549, 'server_script_path': '/w', 'meta': {'domain': 'zh.wikipedia.org', 'partition': 0, 'stream': 'mediawiki.recentchange', 'topic': 'eqiad.mediawiki.recentchange', 'uri': 'https://zh.wikipedia.org/wiki/%E8%88%9E%E6%B3%95%E5%A4%A9%E5%B0%91%E5%A5%B3%E6%9C%B5%E6%B3%95%E6%8B%89%E7%AC%AC%E4%B8%83%E5%AD%A3', 'dt': '2021-09-26T09:08:57Z', 'id': '11f114d4-69ed-451b-a67a-972db14cd7d8', 'request_id': '26d4b058-ebab-41bf-ae48-a5f3c8ed1f61', 'offset': 3323431467}, 'parsedcomment': '<a href="/wiki/Wikipedia:CSD#G3" class="mw-redirect" title="Wikipedia:CSD">G3</a>: 纯粹<a href="/wiki/Wikipedia:VAN" class="mw-redirect" title="Wikipedia:VAN">破坏</a>，包括但不限于明显的<a href="/wiki/Wikipedia:HOAX" class="mw-redirect" title="Wikipedia:HOAX">恶作剧</a>、错误信息、<a href="/wiki/Wikipedia:PA" class="mw-redirect" title="Wikipedia:PA">人身攻击</a>等', 'title': '舞法天少女朵法拉第七季', 'comment': '[[WP:CSD#G3|G3]]: 纯粹[[WP:VAN|破坏]]，包括但不限于明显的[[WP:HOAX|恶作剧]]、错误信息、[[WP:PA|人身攻击]]等', 'bot': False, 'wiki': 'zhwiki', 'type': 'log', 'namespace': 0, 'timestamp': 1632647337, 'log_params': [], '$schema': '/mediawiki/recentchange/1.0.0', 'server_name': 'zh.wikipedia.org', 'server_url': 'https://zh.wikipedia.org', 'log_id': 10844911}

"""

"""
{'type': 'log', 'comment': '机器人: 被永久封禁的用户页', 'id': 138996373, 'server_script_path': '/w', 'wiki': 'zhwiki', 'user': 'Jimmy-abot', 'namespace': 2, 'bot': True, 'parsedcomment': '机器人: 被永久封禁的用户页', 'log_params': {'details': [{'type': 'create', 'expiry': 'infinity', 'level': 'sysop'}], 'cascade': False, 'description': '\u200e[create=sysop] (无限期)'}, 'server_url': 'https://zh.wikipedia.org', 'log_id': 10848695, 'title': 'User:S002282000', '$schema': '/mediawiki/recentchange/1.0.0', 'timestamp': 1632808452, 'server_name': 'zh.wikipedia.org', 'log_action_comment': '保护 User:S002282000 \u200e[create=sysop] (无限期)：机器人: 被永久封禁的用户页', 'meta': {'offset': 3328394438, 'uri': 'https://zh.wikipedia.org/wiki/User:S002282000', 'domain': 'zh.wikipedia.org', 'topic': 'eqiad.mediawiki.recentchange', 'dt': '2021-09-28T05:54:12Z', 'stream': 'mediawiki.recentchange', 'request_id': '292317ad-ca22-4dcd-9e2c-17db5da3da0d', 'id': '07c10791-e6c8-466b-ad8e-37416c534dfa', 'partition': 0}, 'log_action': 'protect', 'log_type': 'protect'}
"""
"""
{'log_id': 10940315, 'parsedcomment': '罕用異體字', '$schema': '/mediawiki/recentchange/1.0.0', 'bot': False, 'id': 139708248, 'log_action': 'move', 'timestamp': 1634616731, 'log_params': {'noredir': '1', 'target': '張為儀'}, 'comment': '罕用異體字', 'type': 'log', 'wiki': 'zhwiki', 'server_url': 'https://zh.wikipedia.org', 'server_name': 'zh.wikipedia.org', 'meta': {'stream': 'mediawiki.recentchange', 'domain': 'zh.wikipedia.org', 'offset': 3374470599, 'id': 'db7893cc-6019-44c1-9027-70a68fe9f71d', 'request_id': 'c336421e-e48b-4911-a023-f7370c8f315d', 'dt': '2021-10-19T04:12:11Z', 'topic': 'eqiad.mediawiki.recentchange', 'partition': 0, 'uri': 'https://zh.wikipedia.org/wiki/%E5%BC%B5%E7%88%B2%E5%84%80'}, 'log_type': 'move', 'log_action_comment': 'moved [[張爲儀]] to [[張為儀]]：罕用異體字', 'title': '張爲儀', 'user': '無聊龍', 'server_script_path': '/w', 'namespace': 0}
"""
