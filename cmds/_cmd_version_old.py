import ssl

def cmd_VERSION(self, localServer, recv):
    try:
        '''
        first = '('
        second = ''
        for key in localServer.chprefix:
            print('wtf: {}'.format(key))
            first += key
            second += localServer.chprefix[key]
        first += ')'
        chprefix = '{}{}'.format(first, second)
        localServer.raw005 = 'MAXTARGETS={} WATCH={} WATCHOPTS=A MODES={} CHANTYPES={} PREFIX={} CHANMODES={} MAXLIST=b:{},e:{},I:{} NICKLEN={} CHANNELLEN={} TOPICLEN={} KICKLEN={} AWAYLEN={} EXTBAN=~,{} NETWORK={}'\
        .format(localServer.maxtargets, localServer.maxwatch, localServer.maxmodes, localServer.chantypes, chprefix, localServer.chmodes, localServer.maxlist['b'], localServer.maxlist['e'], localServer.maxlist['I'],\
        localServer.nicklen, localServer.chanlen, localServer.topiclen, localServer.kicklen, localServer.awaylen, localServer.extBans, localServer.name)
        '''
        self.sendraw(351, '{} {} [{}]'.format(self.server.version, localServer.hostname, localServer.hostinfo))
        if self.ssl:
            self.send('NOTICE', ':{}'.format(ssl.OPENSSL_VERSION))
        self.sendraw('005', '{} :are supported by this server'.format(localServer.raw005))
    except Exception as ex:
        print(ex)
