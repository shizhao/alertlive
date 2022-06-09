import os
import re
import pywikibot
import time


def qstat_status():
    qstat = os.popen('qstat')
    qstat_out = qstat.read()
    if 'alertlive' in qstat_out:
        # print (qstat_out)
        status = re.search(
            r'\d(.*?\s){2}alertlive(.*?\s){2}(?P<status>r|qw|d|E|s|Rr)', qstat_out, re.S).group('status')
        # alert_line = re.search(
        #    r'\n(?P<alert>\d.*?alertlive.*?)\n', qstat_out, re.S).group('alert')
        check = int(re.search(
            r'\n(\d*)\s0.(?P<check>\d*)\salertlive', qstat_out, re.S).group('check'))
    else:
        status = 'd'
        # alert_line = ''
        check = 0
    return (qstat_out, check, status)


def status_out(qstat_data):
    status = qstat_data[2]
    qstat_fullout = qstat_data[0]
    qstat_moreout = os.popen('qstat -j alertlive').read()
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
== 参看 ==
* [[toolforge:sge-jobs/tool/alertlive|在线查看运行状态]]
</noinclude>"""
    text = text % (status, status, status, qstat_fullout, qstat_moreout)
    # print(text)
    site = pywikibot.Site()
    page = pywikibot.Page(site, 'User:Alertlivebot/Status')
    # wikitext = page.text
    page.text = text
    page.save('bot status update: %s' % status)


qstat_data = qstat_status()
initstatus = qstat_data[2]
initcheck = qstat_data[1]
status_out(qstat_data)
print(qstat_data[0])
print('init Status: ', initstatus)

while True:

    qstat_data = qstat_status()
    status = qstat_data[2]
    # alert_line = qstat_data[1]
    check = qstat_data[1]
    if status != initstatus or abs(check - initcheck) > 100:
        status_out(qstat_data)
        print(qstat_data[0])
        print('Status: ', status)
        initstatus = status
        initcheck = check
        print('Status change, sleep...')
    # else:
    #    print ('Status not change, sleep...')
    time.sleep(500)
