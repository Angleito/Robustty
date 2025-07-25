export interface CommandContext {
    command: string;
    songTitle?: string;
    queueLength?: number;
    error?: string;
    [key: string]: any;
}
export declare class KanyeResponseGenerator {
    private responses;
    generateResponse(context: CommandContext): string;
    generateErrorResponse(error: string): string;
    generateGreeting(): string;
    generateAcknowledgment(): string;
    private getRandomResponse;
    addCustomResponse(command: string, category: string, response: string): void;
}
//# sourceMappingURL=KanyeResponseGenerator.d.ts.map