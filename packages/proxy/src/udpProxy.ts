import { WebSocket } from 'ws';
import dgram from 'dgram';

export interface UDPConnections {
  [key: string]: dgram.Socket;
}

export interface UDPMessageQueue {
  [key: string]: string[];
}

export function handleUDPProxy(ws: WebSocket, data: any, udpConnections: UDPConnections, udpQueue: UDPMessageQueue) {
    const { id, action, port, address, message } = data;

    if (!id || !action || (action !== 'bind' && (!port || !address))) {
        ws.send(JSON.stringify({ type: 'udp', status: 'error', message: 'Invalid parameters', id }));
        return;
    }

    if (action === 'bind') {
        if (udpConnections[id]) {
            ws.send(JSON.stringify({ type: 'udp', status: 'error', message: 'Already bound', id }));
            return;
        }

        const udpSocket = dgram.createSocket('udp4');
        udpConnections[id] = udpSocket;
        udpQueue[id] = [];

        udpSocket.on('message', (msg, rinfo) => {
            udpQueue[id].push(msg.toString());
        });

        udpSocket.on('error', (err) => {
            console.error(`UDP socket error: ${err.message}`);
            ws.send(JSON.stringify({ type: 'udp', status: 'error', message: err.message, id }));
            udpSocket.close();
            delete udpConnections[id];
            delete udpQueue[id];
        });

        udpSocket.bind(port, () => {
            console.log(`UDP socket bound to port ${port}`);
            ws.send(JSON.stringify({ type: 'udp', status: 'bound', id }));
        });

    } else if (action === 'send' && udpConnections[id]) {
        const udpSocket = udpConnections[id];
        const msgBuffer = Buffer.from(message);
        udpSocket.send(msgBuffer, port, address, (err) => {
            if (err) {
                console.error(`Error sending UDP message: ${err.message}`);
            } else {
                console.log('UDP message sent');
            }
        });

    } else if (action === 'receive' && udpQueue[id]) {
        const queueLength = udpQueue[id].length;
        const message = udpQueue[id].shift() || '';
        ws.send(JSON.stringify({ type: 'udp', data: message, id, queueLength }));

    } else if (action === 'close' && udpConnections[id]) {
        udpConnections[id].close();
        delete udpConnections[id];
        delete udpQueue[id];
        ws.send(JSON.stringify({ type: 'udp', status: 'closed', id }));
    } else {
        ws.send(JSON.stringify({ type: 'udp', status: 'error', message: 'Invalid action or ID', id }));
    }
}
