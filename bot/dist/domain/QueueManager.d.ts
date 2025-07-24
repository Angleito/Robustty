import { Track } from './types';
export declare class QueueManager {
    private queue;
    private currentIndex;
    private loop;
    add(track: Track): Promise<void>;
    getNext(): Promise<Track | null>;
    getCurrent(): Track | null;
    getQueue(): Track[];
    clear(): void;
    setLoop(mode: 'none' | 'track' | 'queue'): void;
    getLoopMode(): 'none' | 'track' | 'queue';
    remove(index: number): boolean;
    shuffle(): void;
}
//# sourceMappingURL=QueueManager.d.ts.map