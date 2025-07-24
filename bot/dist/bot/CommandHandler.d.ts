import { CommandInteraction } from 'discord.js';
import { MusicBot } from './MusicBot';
export declare class CommandHandler {
    private commands;
    private bot;
    private adminHandler;
    constructor(bot: MusicBot);
    private buildCommands;
    registerCommands(): Promise<void>;
    handleCommand(interaction: CommandInteraction): Promise<void>;
    private showQueue;
    private showNowPlaying;
    private formatDuration;
}
//# sourceMappingURL=CommandHandler.d.ts.map