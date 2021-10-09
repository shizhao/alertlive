import pywikibot,json

site = pywikibot.Site()
AAS_page = pywikibot.Page(site, u"Template:ArticleAlertbotSubscription")
Subscription_list = AAS_page.embeddedin()
#if pywikibot.Page(site,'WikiProject:死亡') in Subscription_list:
#    print('yes')
#print(Subscription_list) #专题列表
#t = page.templatesWithParams()
#
alert_pages = []
for Subscription_page in Subscription_list:
    #print(Subscription_page)
    #获取 专题页面上的所有模板及其参数
    templates_Params = Subscription_page.templatesWithParams()
    #寻找通告页面
    #print(templates_Params)
    for Params_tuple in templates_Params:
        if Params_tuple[0] == AAS_page: #Params_tuple:  (Page('Template:ArticleAlertbotSubscription'), ['sub=條目狀態通告'])
            for Params in Params_tuple[1]:
                #找到参数“sub”指出的通告页面
                #排除“sub=”之后为空的
                if Params[:4] == 'sub=' and len(Params) > 4:
                    alert_title = Params[4:]
                    alert_pagetitle = Subscription_page.title()+"/"+alert_title
                    alert_page = pywikibot.Page(site, alert_pagetitle)
                    #print(alert_pagetitle)
                    if alert_page.exists() and not alert_page.isRedirectPage():
                        alert_pages.append(alert_page)


alert_data = []
alert_template = pywikibot.Page(site, u"Template:ArticleAlertbot")
with open('./alert_data/alert_data.json', 'r') as f:
    local_data = json.load(f)
local_str = json.dumps(local_data)
for alert_page in alert_pages:
    #Template:ArticleAlertbot
    if alert_page.exists() and not alert_page.isRedirectPage():
        templates_Params = alert_page.templatesWithParams()
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
                    alert_page_temp =[]
                    for data in local_data:
                        alert_page_temp.append(data[1]['alert_page']) 
                        if data[1]['alert_page'] == alert_page.title():
                            if banner != data[0]:
                                data[0] = banner
                            if archivetime != data[1]['archivetime']:
                                data[1]['archivetime'] = archivetime
                            if workflows_list != data[1]['workflows']:    
                                data[1]['workflows'] = workflows_list
                    if alert_page.title() not in alert_page_temp:

                        params_data['alert_page'] = alert_page.title()
                        params_data['archivetime'] = archivetime
                        params_data['workflows'] = workflows_list
                        params_data['jsonfile'] = alert_page.title().replace('/','_')+'.json'
                        alert_data.append((banner, params_data))

                    
if local_str != json.dumps(local_data):              
    print('UPDATE: ',local_data)
    with open('./alert_data/alert_data.json', 'w') as f:
        json.dump(local_data, f)

if alert_data:
    print(alert_data)
    with open('./alert_data/alert_data.json', 'w') as f:
        json.dump(alert_data, f)