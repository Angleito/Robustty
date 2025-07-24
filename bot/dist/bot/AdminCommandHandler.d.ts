import { CommandInteraction } from 'discord.js';
import { MusicBot } from './MusicBot';
export declare class AdminCommandHandler {
    private bot;
    private adminRoleId?;
    constructor(bot: MusicBot);
    getCommands(): import("discord.js").SlashCommandSubcommandsOnlyBuilder[];
    handleCommand(interaction: CommandInteraction): Promise<void>;
    private isAdmin;
    private handleAuth;
    private handleStatus;
    private handleRestart;
    private handleStats;
    private handleMetrics;
    private handleErrors;
}
//# sourceMappingURL=AdminCommandHandler.d.ts.map