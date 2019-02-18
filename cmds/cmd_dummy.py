def cmd_DUMMY(self, localServer, recv):
    if len(recv) < 20:
        self.sendraw(461, ':DUMMY You are a dummy!')
        return
    self.sendraw(461, ':DUMMY You think you are so smart...')
