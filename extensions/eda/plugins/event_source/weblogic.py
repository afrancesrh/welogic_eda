
DOCUMENTATION = r'''
module: welogic admin
short_description: event-driven-ansible source plugin for Weblogic Cluster
description:
    - Only retrieves records created after the script began executing
    - This script can be tested outside of ansible-rulebook by specifying environment variables for SN_HOST, SN_USERNAME, SN_PASSWORD, SN_TABLE
author: "Colin McNaughton (@cloin)"
options:
    instance:
        description:
            - URL of ServiceNow instance
        required: true
    username:
        description:
            - Basic auth username
        required: true
    password:
        description:
            - Basic auth password
        required: true
    query:
        description:
            - Records to query
        required: false
        default: sys_created_onONToday@javascript:gs.beginningOfToday()@javascript:gs.endOfToday()
    interval:
        description:
            - Seconds to wait before performing another query
        required: false
        default: 5
notes:
    - This is currently only capable of basic authentication and is used so far only for demo purposes
'''

EXAMPLES = r'''
- name: Watch for new events
    hosts: localhost
    sources:
    - cloin.eda.snow_records:
        instance: https://dev-012345.service-now.com
        username: ansible
        password: ansible
        interval: 1
    rules:
    - name: New record created
        condition: event.sys_id is defined
        action:
        debug:
'''

import asyncio
import time
import os
from deepdiff import DeepDiff
from typing import Any, Dict
import aiohttp

# Entrypoint from ansible-rulebook
async def main(queue: asyncio.Queue, args: Dict[str, Any]):

    instance = args.get("instance")
    username = args.get("username")
    password = args.get("password")
    query    = args.get("query", "links=none")
    interval = int(args.get("interval", 5))

    start_time = time.time()
    start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time))
    saved_records = dict()
    current_records = dict()
    newstates = dict()
    async with aiohttp.ClientSession() as session:
        auth = aiohttp.BasicAuth(login=username, password=password)
        while True:
            async with session.get(f'{instance}/management/weblogic/latest/domainRuntime/serverLifeCycleRuntimes?{query}', auth=auth) as resp:
                if resp.status == 200:

                    records = await resp.json()
                    for record in records['items']:
                        current_records[record['name']]=record['state']
                    if current_records != saved_records:
                        changed=DeepDiff(saved_records,current_records)
                        if 'values_changed' in changed:
                            for key,val in changed['values_changed'].items():
                                newstate = { "wl_event": { key.lstrip("root['").rstrip("']"): val['new_value'] }}
                                await queue.put(newstate)
                        saved_records=current_records.copy()
                else:
                    print(f'Error {resp.status}')
            await asyncio.sleep(interval)

if __name__ == "__main__":
    instance = os.environ.get('WL_HOST')
    username = os.environ.get('WL_USERNAME')
    password = os.environ.get('WL_PASSWORD')

    class MockQueue:
        print(f"Waiting for events on ...")
        async def put(self, event):
            print(event)

    asyncio.run(main(MockQueue(), {"instance": instance, "username": username, "password": password}))
