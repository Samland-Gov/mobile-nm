import { WebSocket } from 'ws';
import dgram from 'dgram';

export interface UDPConnections {
  [key: string]: dgram.Socket;
}


export function handleUDPProxy(ws: WebSocket, data: any, udpConnections: UDPConnections) {
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

        udpSocket.on('message', (msg, rinfo) => {
            ws.send(JSON.stringify({ type: 'tcp', status: 'new_data', data: msg.toString(), id }));
        });

        udpSocket.on('error', (err) => {
            console.error(`UDP socket error: ${err.message}`);
            ws.send(JSON.stringify({ type: 'udp', status: 'error', message: err.message, id }));
            udpSocket.close();
            delete udpConnections[id];
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
    } else if (action === 'close' && udpConnections[id]) {
        udpConnections[id].close();
        delete udpConnections[id];
        ws.send(JSON.stringify({ type: 'udp', status: 'closed', id }));
    } else {
        ws.send(JSON.stringify({ type: 'udp', status: 'error', message: 'Invalid action or ID', id }));
    }
}
