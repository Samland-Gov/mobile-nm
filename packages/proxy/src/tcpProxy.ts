import { WebSocket } from 'ws';
import net from 'net';

export interface TCPConnections {
  [key: string]: net.Socket;
}

export interface TCPMessageQueue {
  [key: string]: string[];
}

export function handleTCPProxy(ws: WebSocket, data: any, tcpConnections: TCPConnections, tcpQueue: TCPMessageQueue) {
    const { id, action, port, address, message } = data;

    if (!id || !action) {
        ws.send(JSON.stringify({ type: 'tcp', status: 'error', message: 'Invalid parameters', id }));
        return;
    }

    if (action === 'connect') {
        if (tcpConnections[id]) {
            ws.send(JSON.stringify({ type: 'tcp', status: 'error', message: 'Already connected', id }));
            return;
        }

        const client = new net.Socket();
        tcpConnections[id] = client;
        tcpQueue[id] = [];

        client.connect(port, address, () => {
            console.log('TCP connection established');
            ws.send(JSON.stringify({ type: 'tcp', status: 'connected', id }));
        });

        client.on('data', (data) => {
            tcpQueue[id].push(data.toString());
        });

        client.on('close', () => {
            console.log('TCP connection closed');
            ws.send(JSON.stringify({ type: 'tcp', status: 'disconnected', id }));
            delete tcpConnections[id];
            delete tcpQueue[id];
        });

        client.on('error', (err) => {
            console.error(`TCP connection error: ${err.message}`);
            ws.send(JSON.stringify({ type: 'tcp', status: 'error', message: err.message, id }));
            delete tcpConnections[id];
            delete tcpQueue[id];
        });

    } else if (action === 'send' && tcpConnections[id]) {
        const client = tcpConnections[id];
        client.write(message);

    } else if (action === 'receive' && tcpQueue[id]) {
        const queueLength = tcpQueue[id].length;
        const message = tcpQueue[id].shift() || '';
        ws.send(JSON.stringify({ type: 'tcp', data: message, id, queueLength }));

    } else if (action === 'close' && tcpConnections[id]) {
        tcpConnections[id].end();
        ws.send(JSON.stringify({ type: 'tcp', status: 'closed', id }));
    } else {
        ws.send(JSON.stringify({ type: 'tcp', status: 'error', message: 'Invalid action or ID', id }));
    }
}
