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
    generateFoodResponse(foodType: 'watermelon' | 'friedChicken' | 'koolAid' | 'general'): string;
    private getRandomResponse;
    addCustomResponse(command: string, category: string, response: string): void;
    generateRandomFoodTalk(): string;
    generateWatermelonTalk(): string;
    generateFriedChickenTalk(): string;
    generateKoolAidTalk(): string;
    generateGeneralFoodTalk(): string;
}
//# sourceMappingURL=KanyeResponseGenerator.d.ts.map