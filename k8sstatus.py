import os
import re
import pywikibot
import time
import datetime


def jobs_status():
    jobs = os.popen('toolforge-jobs show alertlive-k8s')
    # Read the output of the command
    jobs_out = jobs.read()
    # Use a regular expression to search for the job status in the output
    status = re.search(
        r'Status:\s+?\|\s+?(?P<status>.*?)\s+?', jobs_out, re.S).group('status')
    # Return the job status and the full output of the command
    return (status, jobs_out)


def status_out(jobs_data):
    status = jobs_data[0]
    jobs_out = jobs_data[1]

    text = """{{#ifeq: {{{1|n}}}|y|
{{User:Alertlivebot/Status2|status=%s|image=y}}
|
{{notice
|image = {{User:Alertlivebot/Status2|status=%s|image=y}}
|当前[[User:Alertlivebot/Status|运行状态]]：{{User:Alertlivebot/Status2|status=%s|text=y}}<small>（最后检查于~~~~~ {{purge|刷新}}）</small>
}}
}}<noinclude>
==运行状态==
<syntaxhighlight lang="shell-session">
%s
</syntaxhighlight>
== 参看 ==
* [[toolforge:k8s-status/namespaces/tool-alertlive|在线查看运行状态]]
</noinclude>"""
    text = text % (status, status, status, jobs_out)
    site = pywikibot.Site()
    page = pywikibot.Page(site, 'User:Alertlivebot/Status')
    page.text = text
    page.save('bot status update: %s' % status)
    # print(text)


# Get the current time
begin_time = datetime.datetime.now()

# get the initial status of a job
jobs_data = jobs_status()
initstatus = jobs_data[0]

# update a wiki page with the current status of the job
status_out(jobs_data)
print(jobs_data[1])
print('init Status: ', initstatus)

# Start an infinite loop
while True:
    # again to check the current status of the job
    jobs_data = jobs_status()
    status = jobs_data[0]
    # If the status has changed or if more than one day has passed since 'begin_time'
    if status != initstatus or (datetime.datetime.now() - begin_time).days > 0:
        # again to update the wiki page with the new status
        status_out(jobs_data)
        print(jobs_data[1])
        print('Status: ', status)
        # Update the values of 'initstatus' and 'begin_time'
        initstatus = status
        begin_time = datetime.datetime.now()
        print('Status change, sleep...')
    # else:
    #    print ('Status not change, sleep...')
    # Pause for 500 seconds before checking again
    time.sleep(500)
