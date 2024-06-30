interface Subscriber {
    id: string;
    name: string;
    phoneNumber: string;
    location: string;
}

export class HomeLocationRegister {
    private subscribers: Map<string, Subscriber>;

    constructor() {
        this.subscribers = new Map();
    }

    addSubscriber(subscriber: Subscriber): void {
        this.subscribers.set(subscriber.id, subscriber);
    }

    getSubscriber(id: string): Subscriber | undefined {
        return this.subscribers.get(id);
    }

    updateLocation(id: string, newLocation: string): boolean {
        const subscriber = this.subscribers.get(id);
        if (subscriber) {
            subscriber.location = newLocation;
            return true;
        }
        return false;
    }

    removeSubscriber(id: string): boolean {
        return this.subscribers.delete(id);
    }
}
