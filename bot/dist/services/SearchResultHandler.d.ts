import { EmbedBuilder, ActionRowBuilder, MessageActionRowComponentBuilder, ButtonInteraction } from 'discord.js';
import { YouTubeVideo, SearchSession } from '../domain/types';
export declare class SearchResultHandler {
    private redis;
    private readonly SESSION_TTL;
    constructor();
    createSearchSession(userId: string, guildId: string, query: string, results: YouTubeVideo[]): Promise<string>;
    getSearchSession(sessionId: string): Promise<SearchSession | null>;
    deleteSearchSession(sessionId: string): Promise<void>;
    createSearchEmbed(query: string, results: YouTubeVideo[]): EmbedBuilder;
    createSelectionButtons(sessionId: string, resultCount: number): ActionRowBuilder<MessageActionRowComponentBuilder>;
    handleSearchSelection(interaction: ButtonInteraction): Promise<YouTubeVideo | null>;
    isSessionExpired(sessionId: string): Promise<boolean>;
    cleanupExpiredSessions(): Promise<void>;
    private formatDuration;
}
//# sourceMappingURL=SearchResultHandler.d.ts.map