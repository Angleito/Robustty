import { Readable } from 'stream';
export declare class AudioRouter {
    private audioServiceUrl;
    constructor();
    captureStream(instanceId: string): Promise<Readable>;
    stopCapture(instanceId: string): Promise<void>;
    getActiveStreams(): Promise<string[]>;
}
//# sourceMappingURL=AudioRouter.d.ts.map