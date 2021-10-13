import os
import re
import pywikibot
import time


qstat_fullout = os.popen('qstat').read()

qstat_moreout = os.popen('qstat -j alertlive-beta').read()

def qstat_status():
    qstat = os.popen('qstat')
    qstat_out = qstat.read()
    if 'alertlive' in qstat_out:
        #print (qstat_out)
        status = re.search(r'\d(.*?\s){2}alertlive(.*?\s){2}(?P<status>r|qw|d|E|s)',qstat_out,re.S).group('status')
        alert_line = re.search(r'\n(?P<alert>\d.*?alertlive.*?)\n',qstat_out,re.S).group('alert')
    else:
        status = 'd'
        alert_line = ''
    return (qstat_out,alert_line,status)

def status_out(qstat_data):
    status = qstat_data[2]
    qstat_fullout = qstat_data[0]
    qstat_moreout = os.popen('qstat -j alertlive-beta').read()
    text = """{{#ifeq: {{{1|n}}}|y|
{{User:Alertlivebot/Status2|status=%s|image=y}}
|
{{notice
|image = {{User:Alertlivebot/Status2|status=%s|image=y}}
|当前[[User:Alertlivebot/Status|运行状态]]：{{User:Alertlivebot/Status2|status=%s|text=y}}<small>（最后检查于{{#time: Y-m-d H:i:s|{{REVISIONTIMESTAMP:User:Alertlivebot/Status}}}} UTC）[{{purge|刷新}}]</small>
}}
}}<noinclude>
==运行状态==
<syntaxhighlight lang="shell-session">
%s
</syntaxhighlight>

<syntaxhighlight lang="shell-session">
%s
</syntaxhighlight>
</noinclude>"""
    text = text % (status, status, status, qstat_fullout, qstat_moreout)
    #print(text)
    site = pywikibot.Site()
    page = pywikibot.Page(site, 'User:Alertlivebot/Status')
    #wikitext = page.text
    page.text = text
    page.save('bot status update')

qstat_data = qstat_status()
initstatus = qstat_data[1]
status_out(qstat_data)
print(qstat_data[0])
print('init Status: ', qstat_data[2])

while True:

    qstat_data = qstat_status()
    alert_line = qstat_data[1]
    if alert_line != initstatus:
        status_out(qstat_data)
        print(qstat_data[0])
        print('Status: ', qstat_data[2])
        initstatus = alert_line
        print ('Status change, sleep...')
    #else:
    #    print ('Status not change, sleep...')
    time.sleep(30)
