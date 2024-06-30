import WebSocket from 'ws';

export class WebSocketClient {
    private ws: WebSocket;
    private url: string;
    
    constructor(url: string) {
        this.url = url;
        this.ws = new WebSocket(url);

        this.ws.on('open', () => {
            console.log(`Connected to ${url}`);
        });

        this.ws.on('close', () => {
            console.log(`Disconnected from ${url}`);
        });

        this.ws.on('error', (error) => {
            console.error(`Error: ${error.message}`);
        });
    }

    send(message: string) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(message);
        } else {
            console.error(`Failed to send message: WebSocket is not open.`);
        }
    }

    onMessage(callback: (message: string) => void) {
        this.ws.on('message', (data: WebSocket.Data) => {
            if (typeof data === 'string') {
                callback(data);
            } else {
                console.error(`Unexpected message format received.`);
            }
        });
    }

    close() {
        this.ws.close();
    }
}
