"""
/memdebug command
"""

import ircd

import gc
try:
    import objgraph
except:
    pass

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('memdebug')
def memdebug(self, localServer, recv):
    localServer.dnsblCache = {}
    localServer.throttle = {}
    localServer.hostcache = {}
    #for w in dict(localServer.whowas):
    #    del localServer.whowas[w]

    gc.collect()
    del gc.garbage[:]
    if localServer.forked:
        return

    try:
        print('-'*25)
        objgraph.show_most_common_types(limit=20)
        print('-'*25)

        if len(recv) > 1:
            type = recv[1]
            print('Showing type: {}'.format(type))
            obj = objgraph.by_type(type)
            print('Amount: {}'.format(len(obj)))
            #ref = objgraph.show_backrefs([obj], max_depth=10)
            for r in obj:
                #print('-'*10)
                #print(r)
                #if ref:
                #    print('Ref: {}'.format(ref))
                #objgraph.show_refs([obj], filename='/home/y4kuzi/Desktop/NewIRCd/sample-graph.png')
                #objgraph.show_backrefs([obj], filename='/home/y4kuzi/Desktop/NewIRCd/sample-backref-graph.png')

                ### Socket debugger.
                if type == 'socket':
                    inuse = list(filter(lambda s: s.socket == r, localServer.users+localServer.servers))
                    #print('Socket is in use? {}'.format(bool(inuse)))
                    if not inuse and r not in localServer.listen_socks:
                        with open('ref.txt', 'a') as f:
                            f.write('-'*10+'\n')
                            f.write(str(r)+'\n')
                            f.write('Ref:\n')
                            for ref in gc.get_referrers(r):
                                f.write(str(ref)+'\n')
                        try:
                            r.close()
                        except:
                            pass
                        del r

                ### List debugger
                '''
                if type == 'list':
                    if len(r) == 0:
                        continue
                    with open('ref.txt', 'a') as f:
                        f.write('-'*10+'\n')
                        f.write(str(r)+'\n')
                        f.write('Ref:\n')
                        for ref in gc.get_referrers(r):
                            f.write(str(ref)+'\n')

                '''
                #if type == 'module':
                #    print('-'*10)
                #    print(r)

        print('Growth (if any):')
        objgraph.show_growth(limit=10)
    except:
        pass
