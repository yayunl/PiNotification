# Python standard modules
import paramiko
import logging
import socket
import time
from datetime import datetime, timedelta
from getpass import getpass

logging.getLogger("paramiko").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class SSH_Connection:
    def __init__(self, system_ip, user, passw):
        self.ssh = None
        self.transport = None
        self.system = system_ip
        self.username = user
        self.password = passw
        self.cmdItr = 0

    @staticmethod
    def my_handler(title, instructions, prompt_list):
        return [echo and input(prompt) or getpass(prompt) for (prompt, echo) in prompt_list]

    def connect(self):
        try:
            if not self.is_connected():
                logger.debug("Connecting to {0}...".format(self.system))
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(hostname=self.system, port=22, username=self.username, password=self.password)
                self.transport = self.ssh.get_transport()
                if not self.transport.authenticated:
                    self.transport.auth_interactive(username=self.username, handler=SSH_Connection.my_handler)
                return True
            else:
                logger.debug("SSH connection already exists.")
        except IOError as error:
            logger.debug(locals())
            logger.error("Bad hostname. {0}".format(error))
            self.disconnect()
        except paramiko.PasswordRequiredException as error:
            logger.debug(locals())
            logger.error("Bad username. {0}".format(error))
            self.disconnect()
        except paramiko.AuthenticationException as error:
            logger.debug(locals())
            logger.error("Bad password. {0}".format(error))
            self.disconnect()
        except Exception as er:
            logger.debug(locals())
            logger.exception("Exception! Failed to connect to system. ({0})".format(er))
            self.disconnect()

        return False

    def disconnect(self):
        logger.debug("Closing connection from system...")
        if self.ssh:
            self.ssh.close()
        return

    def is_connected(self):
        if self.ssh:
            if self.ssh.get_transport() is not None:
                return self.ssh.get_transport().is_active()
        
        return False
    
    def invoke_shell(self):
        channel = ''
        try:
            channel = self.ssh.invoke_shell()
        except paramiko.ssh_exception.SSHException as e:
            logger.debug(locals())
            logger.exception('Exception raised: Invoke_shell request was rejected or the channel was closed.\r\n {0}'.format(e))
        return channel

    def execute_cmd(self, cmd=""):
        outdata, errdata = [], []
        exit_status = -1
        recv_size = 1024
        # if self.is_connected():
        try:
            channel = self.transport.open_session()
            logger.debug("Executing {0}".format(cmd))
            # The channel will be closed automatically after executing the command
            channel.exec_command(cmd)

            # Until the command exits, read from its stdout and stderr
            # TODO: need to figure out way to exit polling in case the command was not executed
            # http://stackoverflow.com/questions/8464391/what-should-i-do-if-socket-setdefaulttimeout-is-not-working
            # wait for command response for max 1 minute
            timedOutEpochTime = time.time() + 60
            logger.debug('Waiting to receive command execution result...')
            logger.debug('SSH command execution timeout time is {0}.'
                         .format(time.strftime('%H:%M:%S', time.localtime(timedOutEpochTime))))
            
            while not channel.exit_status_ready() and timedOutEpochTime > time.time():
                pass
                # if channel.recv_ready():
                #     outdata.append(channel.recv(recv_size))
                # if channel.recv_stderr_ready():
                #     errdata.append(channel.recv_stderr(recv_size))

            # Command has finished, read exit status
            exit_status = channel.recv_exit_status()

            # Ensure we gobble up all remaining data
            logger.debug('Waiting to gobble up all remaining data...')
            while True:
                logger.debug('.')
                sout_recvd = ''
                try:
                    sout_recvd = channel.recv(recv_size)
                    if not sout_recvd and not channel.recv_ready():
                        break
                    else:
                        outdata.append(sout_recvd)
                except socket.timeout:
                    logger.debug(locals())
                    continue

            logger.debug('Waiting to gobble up all remaining error data...')
            while True:
                logger.debug('.')
                serr_recvd = ''
                try:
                    serr_recvd = channel.recv_stderr(recv_size)
                    if not serr_recvd and not channel.recv_stderr_ready():
                        break
                    else:
                        errdata.append(serr_recvd)
                except socket.timeout:
                    logger.debug(locals())
                    continue

            # Close the channel
            channel.close()
            outdata = b''.join(outdata).decode()
            errdata = b''.join(errdata).decode()
            logger.debug('exit_status: {0}, outdata: {1}, errdata: {2}'.format(exit_status, outdata, errdata))
        # else:
        except Exception as e:
            logger.debug(locals())
            logger.debug("Exception {0} raised.".format(e))
            self.cmdItr += 1
            if self.cmdItr > 3:
                logger.debug('Could not connect to device after 3 iterations.')
                self.cmdItr = 0
                return exit_status, outdata, errdata
            
            logger.info('SSH Session appears to have died.')
            self.disconnect()
            logger.info('Reconnecting to Device...')
            if self.connect():
                logger.debug('Rerunning last command.')
                exit_status, outdata, errdata = self.execute_cmd(cmd)

        return exit_status, outdata, errdata
    
    def send(self, channel, cmd=""):
        outdata, errdata = [], []
        recv_size = 1024
        # if self.is_connected():
        try:
            # Clearing output.
            if channel.recv_ready():
                channel.recv(recv_size)
                
            logger.debug("Executing {0}".format(cmd))
            bytes_sent = 0
            retry = 0
            while bytes_sent != len(str(cmd) + '\n') and retry != 3:
                bytes_sent = channel.send(str(cmd) + '\n')
            
            # Since send is sent in interactive shell, sleep() calls might be needed to allow the server adequate time to process and send data
            time.sleep(1)
        
            # Ensure we gobble up all remaining data
            logger.debug('Waiting to gobble up all remaining data...')
            while True:
                logger.debug('.')
                sout_recvd = ''
                try:
                    sout_recvd = channel.recv(recv_size)
                    outdata.append(sout_recvd)
                    if not channel.recv_ready():
                        break
                except socket.timeout:
                    logger.debug(locals())
                    continue
                
            logger.debug('Waiting to gobble up all remaining error data...')
            while channel.recv_stderr_ready():
                logger.debug('.')
                serr_recvd = ''
                try:
                    serr_recvd = channel.recv_stderr(recv_size)
                    errdata.append(serr_recvd)
                except socket.timeout:
                    logger.debug(locals())
                    continue
        
            outdata = b''.join(outdata).decode()
            errdata = b''.join(errdata).decode()
            logger.debug('outdata: {0}, errdata: {1}'.format(outdata, errdata))
        # else:
        except Exception as e:
            logger.debug(locals())
            logger.debug("Exception {0} raised.".format(e))
            self.cmdItr += 1
            if self.cmdItr > 3:
                logger.debug('Could not connect to device after 3 iterations.')
                self.cmdItr = 0
                return outdata, errdata
    
            logger.info('SSH Session appears to have died.')
            self.disconnect()
            logger.info('Reconnecting to Device...')
            if self.connect():
                logger.debug('Rerunning last command.')
                outdata, errdata = self.send(channel, cmd)
    
        return outdata, errdata

