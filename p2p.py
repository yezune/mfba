#!/usr/bin/env python3

# this code is from berry college Math and CS Department
# More detail, You can see http://cs.berry.edu/~nhamid/p2p/

import socket
import struct
import threading
import time
import traceback
import sys
import random
try:
    import tkinter as tk # python version 3.x
except:
    import Tkinter as tk # python version 2.x


def btdebug(msg):
    """ Prints a messsage to the screen with the name of the current thread """
    print ("[%s] %s" % (str(threading.currentThread().getName()), msg))

class BTPeer:
    """ Implements the core functionality that might be used by a peer in a
    P2P network.
    """

    def __init__(self, maxpeers, serverport, myid=None, serverhost=None):

        """ Initializes a peer servent (sic.) with the ability to catalog
        information for up to maxpeers number of peers (maxpeers may
        be set to 0 to allow unlimited number of peers), listening on
        a given server port , with a given canonical peer name (id)
        and host address. If not supplied, the host address
        (serverhost) will be determined by attempting to connect to an
        Internet host like Google.
        """
        self.debug = 0

        self.maxpeers = int(maxpeers)
        self.serverport = int(serverport)
        if serverhost: self.serverhost = serverhost
        else: self.__initserverhost()

        if myid: self.myid = myid
        else: self.myid = '%s:%d' % (self.serverhost, self.serverport)

        self.peerlock = threading.Lock()  # ensure proper access to
        # peers list (maybe better to use
        # threading.RLock (reentrant))
        self.peers = {}  # peerid ==> (host, port) mapping
        self.shutdown = False  # used to stop the main loop

        self.handlers = {}
        self.router = None


    def __initserverhost(self):

        """ Attempt to connect to an Internet host in order to determine the
        local machine's IP address.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("www.google.com", 80))
        self.serverhost = s.getsockname()[0]
        s.close()


    def __debug(self, msg):

        if self.debug:
            btdebug(msg)


    def __handlepeer(self, clientsock):

        """
        handlepeer( new socket connection ) -> ()
        Dispatches messages from the socket connection
        """

        self.__debug('New child ' + str(threading.currentThread().getName()))
        self.__debug('Connected ' + str(clientsock.getpeername()))

        host, port = clientsock.getpeername()
        peerconn = BTPeerConnection(None, host, port, clientsock, debug=False)

        try:
            msgtype, msgdata = peerconn.recvdata()
            if msgtype: msgtype = msgtype.upper()
            if msgtype not in self.handlers:
                self.__debug('Not handled: %s: %s' % (msgtype, msgdata))
            else:
                self.__debug('Handling peer msg: %s: %s' % (msgtype, msgdata))
                self.handlers[msgtype](peerconn, msgdata)
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()

        self.__debug('Disconnecting ' + str(clientsock.getpeername()))
        peerconn.close()

    # end handlepeer method


    def __runstabilizer(self, stabilizer, delay):

        while not self.shutdown:
            stabilizer()
            time.sleep(delay)


    def setmyid(self, myid):

        self.myid = myid


    def startstabilizer(self, stabilizer, delay):

        """ Registers and starts a stabilizer function with this peer. 
        The function will be activated every <delay> seconds. 

        """
        t = threading.Thread(
            target=self.__runstabilizer, args=[stabilizer, delay])
        t.start()


    def addhandler(self, msgtype, handler):

        """ Registers the handler for the given message type with this peer """
        assert len(msgtype) == 4
        self.handlers[msgtype] = handler


    def addrouter(self, router):

        """ Registers a routing function with this peer. The setup of routing
        is as follows: This peer maintains a list of other known peers
        (in self.peers). The routing function should take the name of
        a peer (which may not necessarily be present in self.peers)
        and decide which of the known peers a message should be routed
        to next in order to (hopefully) reach the desired peer. The router
        function should return a tuple of three values: (next-peer-id, host,
        port). If the message cannot be routed, the next-peer-id should be
        None.

        """
        self.router = router


    def addpeer(self, peerid, host, port):

        """ Adds a peer name and host:port mapping to the known list of peers.

        """
        if peerid not in self.peers and (self.maxpeers == 0
                                         or len(self.peers) < self.maxpeers):
            self.peers[peerid] = (host, int(port))
            return True
        else:
            return False


    def getpeer(self, peerid):

        """ Returns the (host, port) tuple for the given peer name """
        assert peerid in self.peers  # maybe make this just a return NULL?
        return self.peers[peerid]


    def removepeer(self, peerid):

        """ Removes peer information from the known list of peers. """
        if peerid in self.peers:
            del self.peers[peerid]


    def addpeerat(self, loc, peerid, host, port):

        """ Inserts a peer's information at a specific position in the 
        list of peers. The functions addpeerat, getpeerat, and removepeerat
        should not be used concurrently with addpeer, getpeer, and/or 
        removepeer. 

        """
        self.peers[loc] = (peerid, host, int(port))


    def getpeerat(self, loc):

        if loc not in self.peers:
            return None
        return self.peers[loc]


    def removepeerat(self, loc):

        removepeer(self, loc)


    def getpeerids(self):

        """ Return a list of all known peer id's. """
        return self.peers.keys()


    def numberofpeers(self):

        """ Return the number of known peer's. """
        return len(self.peers)

    def maxpeersreached(self):

        """ Returns whether the maximum limit of names has been added to the
        list of known peers. Always returns True if maxpeers is set to
        0.

        """
        assert self.maxpeers == 0 or len(self.peers) <= self.maxpeers
        return self.maxpeers > 0 and len(self.peers) == self.maxpeers


    def makeserversocket(self, port, backlog=5):

        """ Constructs and prepares a server socket listening on the given 
        port.

        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.listen(backlog)
        return s


    def sendtopeer(self, peerid, msgtype, msgdata, waitreply=True):

        """
        sendtopeer( peer id, message type, message data, wait for a reply )
         -> [ ( reply type, reply data ), ... ] 

        Send a message to the identified peer. In order to decide how to
        send the message, the router handler for this peer will be called.
        If no router function has been registered, it will not work. The
        router function should provide the next immediate peer to whom the 
        message should be forwarded. The peer's reply, if it is expected, 
        will be returned.

        Returns None if the message could not be routed.
        """

        if self.router:
            nextpid, host, port = self.router(peerid)
        if not self.router or not nextpid:
            self.__debug('Unable to route %s to %s' % (msgtype, peerid))
            return None
        #host,port = self.peers[nextpid]
        return self.connectandsend(
            host, port, msgtype, msgdata, pid=nextpid, waitreply=waitreply)


    def connectandsend(self,
                       host,
                       port,
                       msgtype,
                       msgdata,
                       pid=None,
                       waitreply=True):

        """
        connectandsend( host, port, message type, message data, peer id,
        wait for a reply ) -> [ ( reply type, reply data ), ... ]

        Connects and sends a message to the specified host:port. The host's
        reply, if expected, will be returned as a list of tuples.

        """
        msgreply = []
        try:
            peerconn = BTPeerConnection(pid, host, port, debug=self.debug)
            peerconn.senddata(msgtype, msgdata)
            self.__debug('Sent %s: %s' % (pid, msgtype))

            if waitreply:
                onereply = peerconn.recvdata()
                while (onereply != (None, None)):
                    msgreply.append(onereply)
                    self.__debug('Got reply %s: %s' % (pid, str(msgreply)))
                    onereply = peerconn.recvdata()
            peerconn.close()
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()

        return msgreply

    # end connectsend method


    def checklivepeers(self):

        """ Attempts to ping all currently known peers in order to ensure that
        they are still active. Removes any from the peer list that do
        not reply. This function can be used as a simple stabilizer.

        """
        todelete = []
        for pid in self.peers:
            isconnected = False
            try:
                self.__debug('Check live %s' % pid)
                host, port = self.peers[pid]
                peerconn = BTPeerConnection(pid, host, port, debug=self.debug)
                peerconn.senddata('PING', '')
                isconnected = True
            except:
                todelete.append(pid)
            if isconnected:
                peerconn.close()

        self.peerlock.acquire()
        try:
            for pid in todelete:
                if pid in self.peers: del self.peers[pid]
        finally:
            self.peerlock.release()

    # end checklivepeers method


    def mainloop(self):

        s = self.makeserversocket(self.serverport)
        s.settimeout(2)
        self.__debug('Server started: %s (%s:%d)' %
                     (self.myid, self.serverhost, self.serverport))

        while not self.shutdown:
            try:
                self.__debug('Listening for connections...')
                clientsock, clientaddr = s.accept()
                clientsock.settimeout(None)

                t = threading.Thread(
                    target=self.__handlepeer, args=[clientsock])
                t.start()
            except KeyboardInterrupt:
                print ('KeyboardInterrupt: stopping mainloop')
                self.shutdown = True
                continue
            except:
                if self.debug:
                    traceback.print_exc()
                    continue

        # end while loop
        self.__debug('Main loop exiting')

        s.close()

    # end mainloop method


# end BTPeer class

# **********************************************************


class BTPeerConnection:


    def __init__(self, peerid, host, port, sock=None, debug=False):

        # any exceptions thrown upwards

        self.id = peerid
        self.debug = debug

        if not sock:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((host, int(port)))
        else:
            self.s = sock

        self.sd = self.s.makefile('rw', 0)


    def __makemsg(self, msgtype, msgdata):

        msglen = len(msgdata)
        msg = struct.pack("!4sL%ds" % msglen, msgtype, msglen, msgdata)
        return msg


    def __debug(self, msg):

        if self.debug:
            btdebug(msg)


    def senddata(self, msgtype, msgdata):
        """
        senddata( message type, message data ) -> boolean status
        Send a message through a peer connection. Returns True on success
        or False if there was an error.
        """

        try:
            msg = self.__makemsg(msgtype, msgdata)
            self.sd.write(msg)
            self.sd.flush()
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
            return False
        return True


    def recvdata(self):
        """
        recvdata() -> (msgtype, msgdata)
        Receive a message from a peer connection. Returns (None, None)
        if there was any error.
        """
        try:
            msgtype = self.sd.read(4)
            if not msgtype: return (None, None)

            lenstr = self.sd.read(4)
            msglen = int(struct.unpack("!L", lenstr)[0])
            msg = ""

            while len(msg) != msglen:
                data = self.sd.read(min(2048, msglen - len(msg)))
                if not len(data):
                    break
                msg += data

            if len(msg) != msglen:
                return (None, None)

        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
            return (None, None)

        return (msgtype, msg)

    # end recvdata method

    def close(self):
        """
        close()
        Close the peer connection. The send and recv methods will not work
        after this call.
        """
        self.s.close()
        self.s = None
        self.sd = None

    def __str__(self):

        return "|%s|" % peerid

#---------------------
# P2P File transfer
#---------------------

PEERNAME = "NAME"  # request a peer's canonical id
LISTPEERS = "LIST"
INSERTPEER = "JOIN"
QUERY = "QUER"
QRESPONSE = "RESP"
FILEGET = "FGET"
PEERQUIT = "QUIT"
REPLY = "REPL"
ERROR = "ERRO"

# Assumption in this program:
#   peer id's in this application are just "host:port" strings

class FilerPeer(BTPeer):
    """ Implements a file-sharing peer-to-peer entity based on the generic
    BerryTella P2P framework.
    """
    def __init__(self, maxpeers, serverport):
        """ Initializes the peer to support connections up to maxpeers number
        of peers, with its server listening on the specified port. Also sets
        the dictionary of local files to empty and adds handlers to the 
        BTPeer framework.
        """
        BTPeer.__init__(self, maxpeers, serverport)

        self.files = {}  # available files: name --> peerid mapping

        self.addrouter(self.__router)

        handlers = {
            LISTPEERS: self.__handle_listpeers,
            INSERTPEER: self.__handle_insertpeer,
            PEERNAME: self.__handle_peername,
            QUERY: self.__handle_query,
            QRESPONSE: self.__handle_qresponse,
            FILEGET: self.__handle_fileget,
            PEERQUIT: self.__handle_quit
        }
        for mt in handlers:
            self.addhandler(mt, handlers[mt])

    # end FilerPeer constructor

    def __debug(self, msg):
        if self.debug:
            btdebug(msg)

    def __router(self, peerid):
        if peerid not in self.getpeerids():
            return (None, None, None)
        else:
            rt = [peerid]
            rt.extend(self.peers[peerid])
            return rt

    def __handle_insertpeer(self, peerconn, data):
        """ Handles the INSERTPEER (join) message type. The message data
                should be a string of the form, "peerid  host  port", where peer-id
                is the canonical name of the peer that desires to be added to this
                peer's list of peers, host and port are the necessary data to connect
                to the peer.
                """
        self.peerlock.acquire()
        try:
            try:
                peerid, host, port = data.split()

                if self.maxpeersreached():
                    self.__debug('maxpeers %d reached: connection terminating'
                                 % self.maxpeers)
                    peerconn.senddata(ERROR, 'Join: too many peers')
                    return

                # peerid = '%s:%s' % (host,port)
                if peerid not in self.getpeerids() and peerid != self.myid:
                    self.addpeer(peerid, host, port)
                    self.__debug('added peer: %s' % peerid)
                    peerconn.senddata(REPLY, 'Join: peer added: %s' % peerid)
                else:
                    peerconn.senddata(
                        ERROR, 'Join: peer already inserted %s' % peerid)
            except:
                self.__debug('invalid insert %s: %s' % (str(peerconn), data))
                peerconn.senddata(ERROR, 'Join: incorrect arguments')
        finally:
            self.peerlock.release()

    # end handle_insertpeer method

    def __handle_listpeers(self, peerconn, data):
        """ Handles the LISTPEERS message type. Message data is not used. """
        self.peerlock.acquire()
        try:
            self.__debug('Listing peers %d' % self.numberofpeers())
            peerconn.senddata(REPLY, '%d' % self.numberofpeers())
            for pid in self.getpeerids():
                host, port = self.getpeer(pid)
                peerconn.senddata(REPLY, '%s %s %d' % (pid, host, port))
        finally:
            self.peerlock.release()

    def __handle_peername(self, peerconn, data):
        """ Handles the NAME message type. Message data is not used. """
        peerconn.senddata(REPLY, self.myid)

    # QUERY arguments: "return-peerid key ttl"
    def __handle_query(self, peerconn, data):
        """ Handles the QUERY message type. The message data should be in the
        format of a string, "return-peer-id  key  ttl", where return-peer-id
        is the name of the peer that initiated the query, key is the (portion
        of the) file name being searched for, and ttl is how many further 
        levels of peers this query should be propagated on.
        """
        # self.peerlock.acquire()
        try:
            peerid, key, ttl = data.split()
            peerconn.senddata(REPLY, 'Query ACK: %s' % key)
        except:
            self.__debug('invalid query %s: %s' % (str(peerconn), data))
            peerconn.senddata(ERROR, 'Query: incorrect arguments')
        # self.peerlock.release()

        t = threading.Thread(
            target=self.__processquery, args=[peerid, key,
                                              int(ttl)])
        t.start()

    def __processquery(self, peerid, key, ttl):
        """ Handles the processing of a query message after it has been 
        received and acknowledged, by either replying with a QRESPONSE message
        if the file is found in the local list of files, or propagating the
        message onto all immediate neighbors.
        """
        for fname in self.files.keys():
            if key in fname:
                fpeerid = self.files[fname]
                if not fpeerid:  # local files mapped to None
                    fpeerid = self.myid
                host, port = peerid.split(':')
                # can't use sendtopeer here because peerid is not necessarily
                # an immediate neighbor
                self.connectandsend(
                    host,
                    int(port),
                    QRESPONSE,
                    '%s %s' % (fname, fpeerid),
                    pid=peerid)
                return
        # will only reach here if key not found... in which case
        # propagate query to neighbors
        if ttl > 0:
            msgdata = '%s %s %d' % (peerid, key, ttl - 1)
            for nextpid in self.getpeerids():
                self.sendtopeer(nextpid, QUERY, msgdata)

    def __handle_qresponse(self, peerconn, data):
        """ Handles the QRESPONSE message type. The message data should be
        in the format of a string, "file-name  peer-id", where file-name is
        the file that was queried about and peer-id is the name of the peer
        that has a copy of the file.

        """
        try:
            fname, fpeerid = data.split()
            if fname in self.files:
                self.__debug('Can\'t add duplicate file %s %s' % (fname,
                                                                  fpeerid))
            else:
                self.files[fname] = fpeerid
        except:
            #if self.debug:
            traceback.print_exc()

    def __handle_fileget(self, peerconn, data):
        """ Handles the FILEGET message type. The message data should be in
        the format of a string, "file-name", where file-name is the name
        of the file to be fetched.

        """
        fname = data
        if fname not in self.files:
            self.__debug('File not found %s' % fname)
            peerconn.senddata(ERROR, 'File not found')
            return
        try:
            fd = file(fname, 'r')
            filedata = ''
            while True:
                data = fd.read(2048)
                if not len(data):
                    break
                filedata += data
            fd.close()
        except:
            self.__debug('Error reading file %s' % fname)
            peerconn.senddata(ERROR, 'Error reading file')
            return

        peerconn.senddata(REPLY, filedata)

    def __handle_quit(self, peerconn, data):
        """ Handles the QUIT message type. The message data should be in the
        format of a string, "peer-id", where peer-id is the canonical
        name of the peer that wishes to be unregistered from this
        peer's directory.
        """
        self.peerlock.acquire()
        try:
            peerid = data.lstrip().rstrip()
            if peerid in self.getpeerids():
                msg = 'Quit: peer removed: %s' % peerid
                self.__debug(msg)
                peerconn.senddata(REPLY, msg)
                self.removepeer(peerid)
            else:
                msg = 'Quit: peer not found: %s' % peerid
                self.__debug(msg)
                peerconn.senddata(ERROR, msg)
        finally:
            self.peerlock.release()

    # precondition: may be a good idea to hold the lock before going
    #               into this function
    def buildpeers(self, host, port, hops=1):
        """ buildpeers(host, port, hops) 
                Attempt to build the local peer list up to the limit stored by
                self.maxpeers, using a simple depth-first search given an
                initial host and port as starting point. The depth of the
                search is limited by the hops parameter.
                """
        if self.maxpeersreached() or not hops:
            return

        peerid = None

        self.__debug("Building peers from (%s,%s)" % (host, port))

        try:
            _, peerid = self.connectandsend(host, port, PEERNAME, '')[0]

            self.__debug("contacted " + peerid)
            resp = self.connectandsend(host, port, INSERTPEER, '%s %s %d' %
                                       (self.myid, self.serverhost,
                                        self.serverport))[0]
            self.__debug(str(resp))
            if (resp[0] != REPLY) or (peerid in self.getpeerids()):
                return

            self.addpeer(peerid, host, port)

            # do recursive depth first search to add more peers
            resp = self.connectandsend(host, port, LISTPEERS, '', pid=peerid)
            if len(resp) > 1:
                resp.reverse()
                resp.pop()  # get rid of header count reply
                while len(resp):
                    nextpid, host, port = resp.pop()[1].split()
                    if nextpid != self.myid:
                        self.buildpeers(host, port, hops - 1)
        except:
            if self.debug:
                traceback.print_exc()
            self.removepeer(peerid)

    def addlocalfile(self, filename):
        """ Registers a locally-stored file with the peer. """
        self.files[filename] = None
        self.__debug("Added local file %s" % filename)

#----------------------
# P2P file transfer GUI 
#----------------------

class BTGui(tk.Frame):
   def __init__( self, firstpeer, hops=2, maxpeers=5, serverport=5678, master=None ):
      tk.Frame.__init__( self, master )
      self.grid()
      self.createWidgets()
      self.master.title( "BerryTella Filer GUI %d" % serverport )
      self.btpeer = FilerPeer( maxpeers, serverport )
      
      self.bind( "<Destroy>", self.__onDestroy )

      host,port = firstpeer.split(':')
      self.btpeer.buildpeers( host, int(port), hops=hops )
      self.updatePeerList()

      t = threading.Thread( target = self.btpeer.mainloop, args = [] )
      t.start()
      
      self.btpeer.startstabilizer( self.btpeer.checklivepeers, 3 )
#      self.btpeer.startstabilizer( self.onRefresh, 3 )
      self.after( 3000, self.onTimer )
      
      
   def onTimer( self ):
      self.onRefresh()
      self.after( 3000, self.onTimer )
      #self.after_idle( self.onTimer )

      
   def __onDestroy( self, event ):
      self.btpeer.shutdown = True


   def updatePeerList( self ):
      if self.peerList.size() > 0:
         self.peerList.delete(0, self.peerList.size() - 1)
      for p in self.btpeer.getpeerids():
         self.peerList.insert( tk.END, p )


   def updateFileList( self ):
      if self.fileList.size() > 0:
         self.fileList.delete(0, self.fileList.size() - 1)
      for f in self.btpeer.files:
         p = self.btpeer.files[f]
         if not p:
            p = '(local)'
         self.fileList.insert( tk.END, "%s:%s" % (f,p) )
      
      
   def createWidgets( self ):
      """
      Set up the frame widgets
      """
      fileFrame = tk.Frame(self)
      peerFrame = tk.Frame(self)

      rebuildFrame = tk.Frame(self)
      searchFrame = tk.Frame(self)
      addfileFrame = tk.Frame(self)
      pbFrame = tk.Frame(self)
      
      fileFrame.grid(row=0, column=0, sticky=tk.N+tk.S)
      peerFrame.grid(row=0, column=1, sticky=tk.N+tk.S)
      pbFrame.grid(row=2, column=1)
      addfileFrame.grid(row=3)
      searchFrame.grid(row=4)
      rebuildFrame.grid(row=3, column=1)
      
      tk.Label( fileFrame, text='Available Files' ).grid()
      tk.Label( peerFrame, text='Peer List' ).grid()
      
      fileListFrame = tk.Frame(fileFrame)
      fileListFrame.grid(row=1, column=0)
      fileScroll = tk.Scrollbar( fileListFrame, orient=tk.VERTICAL )
      fileScroll.grid(row=0, column=1, sticky=tk.N+tk.S)

      self.fileList = tk.Listbox(fileListFrame, height=5, 
                        yscrollcommand=fileScroll.set)
      #self.fileList.insert( tk.END, 'a', 'b', 'c', 'd', 'e', 'f', 'g' )
      self.fileList.grid(row=0, column=0, sticky=tk.N+tk.S)
      fileScroll["command"] = self.fileList.yview

      self.fetchButton = tk.Button( fileFrame, text='Fetch',
                           command=self.onFetch)
      self.fetchButton.grid()
      
      self.addfileEntry = tk.Entry(addfileFrame, width=25)
      self.addfileButton = tk.Button(addfileFrame, text='Add',
                           command=self.onAdd)
      self.addfileEntry.grid(row=0, column=0)
      self.addfileButton.grid(row=0, column=1)
      
      self.searchEntry = tk.Entry(searchFrame, width=25)
      self.searchButton = tk.Button(searchFrame, text='Search', 
                           command=self.onSearch)
      self.searchEntry.grid(row=0, column=0)
      self.searchButton.grid(row=0, column=1)
      
      peerListFrame = tk.Frame(peerFrame)
      peerListFrame.grid(row=1, column=0)
      peerScroll = tk.Scrollbar( peerListFrame, orient=tk.VERTICAL )
      peerScroll.grid(row=0, column=1, sticky=tk.N+tk.S)
      
      self.peerList = tk.Listbox(peerListFrame, height=5,
                        yscrollcommand=peerScroll.set)
      #self.peerList.insert( tk.END, '1', '2', '3', '4', '5', '6' )
      self.peerList.grid(row=0, column=0, sticky=tk.N+tk.S)
      peerScroll["command"] = self.peerList.yview
      
      self.removeButton = tk.Button( pbFrame, text='Remove',
                                  command=self.onRemove )
      self.refreshButton = tk.Button( pbFrame, text = 'Refresh', 
                            command=self.onRefresh )

      self.rebuildEntry = tk.Entry(rebuildFrame, width=25)
      self.rebuildButton = tk.Button( rebuildFrame, text = 'Rebuild', 
                            command=self.onRebuild )
      self.removeButton.grid(row=0, column=0)
      self.refreshButton.grid(row=0, column=1)
      self.rebuildEntry.grid(row=0, column=0)
      self.rebuildButton.grid(row=0, column=1)      
      
      
      # print "Done"
      
      
   def onAdd(self):
      file = self.addfileEntry.get()
      if file.lstrip().rstrip():
         filename = file.lstrip().rstrip()
         self.btpeer.addlocalfile( filename )
      self.addfileEntry.delete( 0, len(file) )
      self.updateFileList()


   def onSearch(self):
      key = self.searchEntry.get()
      self.searchEntry.delete( 0, len(key) )

      for p in self.btpeer.getpeerids():
         self.btpeer.sendtopeer( p, 
                                 QUERY, "%s %s 4" % ( self.btpeer.myid, key ) )


   def onFetch(self):
      sels = self.fileList.curselection()
      if len(sels)==1:
         sel = self.fileList.get(sels[0]).split(':')
         if len(sel) > 2:  # fname:host:port
            fname,host,port = sel
            resp = self.btpeer.connectandsend( host, port, FILEGET, fname )
            if len(resp) and resp[0][0] == REPLY:
               fd = file( fname, 'w' )
               fd.write( resp[0][1] )
               fd.close()
               self.btpeer.files[fname] = None  # because it's local now


   def onRemove(self):
      sels = self.peerList.curselection()
      if len(sels)==1:
         peerid = self.peerList.get(sels[0])
         self.btpeer.sendtopeer( peerid, PEERQUIT, self.btpeer.myid )
         self.btpeer.removepeer( peerid )


   def onRefresh(self):
      self.updatePeerList()
      self.updateFileList()


   def onRebuild(self):
      if not self.btpeer.maxpeersreached():
         peerid = self.rebuildEntry.get()
         self.rebuildEntry.delete( 0, len(peerid) )
         peerid = peerid.lstrip().rstrip()
         try:
            host,port = peerid.split(':')
            #print "doing rebuild", peerid, host, port
            self.btpeer.buildpeers( host, port, hops=3 )
         except:
            if self.btpeer.debug:
               traceback.print_exc()
#         for peerid in self.btpeer.getpeerids():
#            host,port = self.btpeer.getpeer( peerid )


def main():
   if len(sys.argv) < 4:
      print ("Syntax: %s server-port max-peers peer-ip:port" % sys.argv[0])
      sys.exit(-1)

   serverport = int(sys.argv[1])
   maxpeers = sys.argv[2]
   peerid = sys.argv[3]
   app = BTGui( firstpeer=peerid, maxpeers=maxpeers, serverport=serverport )
   app.mainloop()


# setup and run app
if __name__=='__main__':
   main()
