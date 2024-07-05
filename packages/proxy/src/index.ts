import { WebSocketServer, WebSocket } from 'ws';
import { handleUDPProxy, UDPConnections } from './udpProxy';
import { handleTCPProxy, TCPConnections } from './tcpProxy';

const port = 8080;
const wss = new WebSocketServer({ port: port });

// Store connections and message queues per WebSocket client
interface ClientConnections {
    udp: UDPConnections;
    tcp: TCPConnections;
}
const clients: Map<WebSocket, ClientConnections> = new Map();

wss.on('connection', (ws) => {
    console.log('WebSocket connection established');

    const clientConnections: ClientConnections = { udp: {}, tcp: {}};
    clients.set(ws, clientConnections);

    ws.on('message', (message) => {
        try {
            const { type, data } = JSON.parse(message.toString());

            switch (type) {
                case 'udp':
                    handleUDPProxy(ws, data, clientConnections.udp);
                    break;
                case 'tcp':
                    handleTCPProxy(ws, data, clientConnections.tcp);
                    break;
                default:
                    console.error('Unknown proxy type');
            }
        } catch (error) {
            console.error('Error processing message:', error);
            ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format' }));
        }
    });

    ws.on('close', () => {
        console.log('WebSocket connection closed');
        // Cleanup connections for this client
        for (const id in clientConnections.udp) {
            clientConnections.udp[id].close();
            delete clientConnections.udp[id];
        }
        for (const id in clientConnections.tcp) {
            clientConnections.tcp[id].end();
            delete clientConnections.tcp[id];
        }
        clients.delete(ws);
    });

    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        ws.close(); // Close WebSocket on error and trigger cleanup
    });
});

console.log(`WebSocket server listening on ws://localhost:${port}`);
