import datetime
#import pywikibot
csdcat = 'Category:快速删除候选'
filecsd_cats = ['Category:來源不明檔案','Category:可被替代的非自由版权文件','Category:明顯侵權檔案','Category:未知版权的档案','Category:没有合理使用依据的文件','Category:未被条目使用的合理使用档案','Category:可以被取代的圖片']
vfdcat = ['Category:条目删除候选','Category:存废讨论','Category:页面分类删除候选','Category:模板删除候选','Category:用户页删除候选']
ifdcat = 'Category:文件删除候选'
transwikicat = ['Category:移动到维基学院候选','Category:移动到维基导游候选', 'Category:移动到维基教科书候选', 'Category:移动到维基文库候选', 'Category:移动到维基词典候选', 'Category:移动到维基语录候选']
copyviocat = 'Category:怀疑侵犯版权页面'
drvcat = 'Category:存废复核候选'

dykccat = 'Category:新條目推薦候選'
dykcat = 'Category:推薦的新條目'

flccat = 'Category:特色列表候選'
flcat = 'Category:特色列表'
flfcat = 'Category:特色列表落選'
fflcat = 'Category:已撤销的特色列表'

faccat = 'Category:典範條目候選'
facat = 'Category:典范条目'
fafcat = 'Category:典範條目落選'
falcat = 'Category:已撤銷的典範條目'

gancat= 'Category:優良條目評選'
gacat = 'Category:優良條目'
gafcat = 'Category:優良條目落選'
galcat = 'Category:已撤銷的優良條目'

prcat = 'Category:维基百科同行评审'
predcat = 'Category:已同行評審的條目'

splitcat = 'Category:需要分割的条目'

#substubcat = 'Category:%d月小小作品' % time.localtime().tm_mon
substub =[]
for m in range(1,13):
    substub.append('Category:%d月小小作品' % m)
substubcat = substub

def getnotabilitycats(date, n):
    m = date.month
    y = date.year
    for i in range(n):
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    return 'Category:自%s年%s月主題關注度不足的條目' % (y, m)
date = datetime.datetime.today()
notabilitycat = [getnotabilitycats(date, n) for n in range(12)]
#site = pywikibot.Site()
#notabilitycat = [catpage.title() for catpage in pywikibot.Category(site,'Category:主題關注度不足的條目').subcategories()]
#notabilitycat = 'Category:自%d年%d月主題關注度不足的條目' % (time.localtime().tm_year,time.localtime().tm_mon)

cache_format = {'CSD':[],'FCSD':[],'VFD':[],'IFD':[],'TRANS':[],'COPYVIO':[],'DRV':[],'DYK':[],'FC':[],'GA':[],'PR':[],'SPLIT':[],'SUB':[],'FAME':[],'PP':[]}

changecat = {'add': r'^\[\[:(.*?)\]\]已(.*?)至分类', 'remove':r'^\[\[:(.*?)\]\]已从分类中(.*?)(，|$)'}
alertcat = 'Category:用于专题的条目通告'


alert_types = {'页面存废':['VFD','IFD','DRV'],'侵权':['COPYVIO'],'快速删除':['CSD','FCSD'],'新条目推荐':['DYK'],'特色内容':['FC'],'优良条目':['GA'],'同行评审':['PR'],'拆分':['SPLIT'],'小小作品':['SUB'],'关注度':['FAME'],'保护':['PP'],'迁移到其他计划':['TRANS']}
