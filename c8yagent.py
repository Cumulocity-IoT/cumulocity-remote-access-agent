import logging
from logging.handlers import RotatingFileHandler
import paho.mqtt.client as mqtt
from device_proxy import DeviceProxy, WebSocketFailureException
import sys
import time

device_id = "1234567890"
baseurl = "mqtt.cumulocity.com"
tenant = '<tenantId>'
user = '<user>'
password = '<password>'
token = None

remote_access_op_template = 'da600'
fragment = 'c8y_RemoteAccessConnect'
template_id = 'remoteConnect'

tcp_buffer_size = 1024

logger = logging.getLogger('C8YAgent')
loglevel = 'INFO'
logger.setLevel(loglevel)
logHandler = RotatingFileHandler('C8YAgent.log', maxBytes=1 * 1024 * 1024, backupCount=5)
log_formatter = logging.Formatter('%(asctime)s %(threadName)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
logger.addHandler(logHandler)

is_close = False

receivedMessages = []

def on_log(client, userdata, level, buf):
    logger.debug(f'MQTT Debug log: {buf}')

def connect(device_id):
    logger.info('MQTT Client connecting to C8Y...')
    mqttClient = mqtt.Client(client_id=device_id)
    mqttClient.username_pw_set(f'{tenant}/{user}', password)
    mqttClient.on_message = on_message
    mqttClient.on_publish = on_publish
    mqttClient.on_connect = on_connect
    mqttClient.connect(baseurl, 1883)
    mqttClient.loop_start()
    mqttClient.on_log = on_log
    return mqttClient

def stop():
    is_close = True
    disconnect(mqttClient, device_id)

def disconnect(mqttClient, device_id):
    mqttClient.loop_stop()  # stop the loop
    mqttClient.disconnect()
    logger.info("Disconnecting MQTT Client")

def set_executing(mqttClient, fragment):
    publish(mqttClient, "s/us", f'501,{fragment}', False)

def set_failed(mqttClient, fragment, failureReason):
    publish(mqttClient, "s/us", f'502,{fragment},{failureReason}', False)
    
def set_success(mqttClient, fragment):
    publish(mqttClient, "s/us", f'503,{fragment}', False)

def proxy_connect(message):
        """
        Creates the Device Proxy and connects to WebSocket and TCP Port
        """
        tcp_host = message[2]
        tcp_port = int(message[3])
        connection_key = message[4]

        if token is None and tenant is None and user is None and password is None:
            raise WebSocketFailureException(
                'OAuth Token or tenantuser and password must be provided!')
         # Not sure which buffer size is good, starting with 16 KB (16 x 1024)
        device_proxy = DeviceProxy(
            tcp_host, tcp_port, tcp_buffer_size, connection_key, baseurl, tenant, user, password, token)
        device_proxy.connect()
        set_success(mqttClient, fragment)


def on_message(client, userdata, message):
    try:
        logger.info("Received operation '{0}'".format(str(message.payload)))
        payload = message.payload.decode("utf-8")
        payload_array = payload.split(',')
        if payload_array[0] == remote_access_op_template:
            set_executing(client, fragment)
            proxy_connect(payload_array)
    except Exception as ex:
         logging.error(f'Handling operation error. exception={ex}')
         set_failed(mqttClient, fragment, str(ex))
        

def on_publish(client, userdata, mid):
    # receivedMessages.append(mid)
    logger.debug("mid: '{0}".format(mid))

def on_connect(client, userdata, flag, rc):
    if rc==0:
        logger.info('MQTT Client succesfully connected!')
        subscribe(mqttClient, 's/e',0)
        subscribe(mqttClient, 's/ds',0)
        subscribe(mqttClient, f's/dc/{template_id}',0)
        publish(mqttClient, "s/us", "100,Remote Access Demo Device " + device_id + ",c8y_RemoteAccessDemoDevice", False)
        publish(mqttClient, "s/us", f'114,{fragment}', False)
    else:
        disconnect(mqttClient, device_id)

def publish(mqttClient, topic, message, waitForAck=False):
    logger.debug("Publishing: '{0}' | '{1}' | '{2}'".format(topic, message, str(waitForAck)))
    mid = mqttClient.publish(topic, message, 2)[1]
    if (waitForAck):
        while mid not in receivedMessages:
            time.sleep(0.25)



def subscribe(mqttClient, topic, qos):
    mqttClient.subscribe(topic, qos)

def mqtt_loop():
    while not is_close:
        try:
            logger.debug('Looping Cycle')
            time.sleep(10)
        except Exception as e:
            disconnect(mqttClient, device_id)
            if isinstance(e, KeyboardInterrupt):
                sys.exit()
            logger.error("Error on processing payload '{0}'".format(e))
    

if __name__ == "__main__":
    mqttClient = connect(device_id)
    mqtt_loop()
     # ----------Register device(s)----------------------------------



