import WebSocket, { Server } from 'ws';

export interface Client {
    ws: WebSocket;
}

export class WebSocketServer {
    private wss: Server;
    private clients: Set<Client>;

    constructor(port: number, onMessageCallback: (message: string, client: Client) => void) {
        this.wss = new Server({ port });
        this.clients = new Set();

        this.wss.on('connection', (ws: WebSocket) => {
            const client: Client = { ws };
            this.clients.add(client);

            ws.on('message', (message: WebSocket.Data) => {
                if (typeof message === 'string') {
                    onMessageCallback(message, client);
                } else {
                    console.error(`Unexpected message format received.`);
                }
            });

            ws.on('close', () => {
                this.clients.delete(client);
            });

            ws.on('error', (error) => {
                console.error(`Error: ${error.message}`);
            });

            console.log(`Client connected.`);
        });

        console.log(`WebSocket server started on port ${port}`);
    }

    send(client: Client, message: string) {
        if (client.ws.readyState === WebSocket.OPEN) {
            client.ws.send(message);
        } else {
            console.error(`Failed to send message: WebSocket is not open.`);
        }
    }

    broadcast(message: string, sender: Client) {
        for (const client of this.clients) {
            if (client !== sender) {
                this.send(client, message);
            }
        }
    }
}
