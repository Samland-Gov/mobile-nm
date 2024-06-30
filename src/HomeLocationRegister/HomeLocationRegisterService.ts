import { HomeLocationRegister } from './HomeLocationRegister';
import { Client, WebSocketServer } from '../Shared/WebSocketServer';

export const startHLRService = (port: number) => {
    const hlr = new HomeLocationRegister();

    const onMessage = (message: string, client: Client) => {
        const data = JSON.parse(message);

        switch (data.action) {
            case 'addSubscriber':
                hlr.addSubscriber(data.subscriber);
                console.log(`Subscriber added: ${JSON.stringify(data.subscriber)}`);
                break;
            case 'getSubscriber':
                const subscriber = hlr.getSubscriber(data.id);
                if (subscriber) {
                    server.send(client, JSON.stringify({ action: 'getSubscriber', subscriber }));
                } else {
                    server.send(client, JSON.stringify({ action: 'getSubscriber', error: 'Subscriber not found' }));
                }
                break;
            case 'updateLocation':
                const success = hlr.updateLocation(data.id, data.newLocation);
                server.send(client, JSON.stringify({ action: 'updateLocation', success }));
                break;
            case 'removeSubscriber':
                const removed = hlr.removeSubscriber(data.id);
                server.send(client, JSON.stringify({ action: 'removeSubscriber', success: removed }));
                break;
            default:
                console.error(`Unknown action: ${data.action}`);
        }
    };

    const server = new WebSocketServer(port, onMessage);

    console.log(`Home Location Register service started on port ${port}`);
};
