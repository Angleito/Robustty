import { ButtonInteraction, ActionRowBuilder, MessageActionRowComponentBuilder } from 'discord.js';
import { MusicBot } from './MusicBot';
export declare class ButtonHandler {
    private bot;
    constructor(bot: MusicBot);
    createPlayerControls(): ActionRowBuilder<MessageActionRowComponentBuilder>;
    createQueueControls(page: number, totalPages: number): ActionRowBuilder<MessageActionRowComponentBuilder>;
    handleButton(interaction: ButtonInteraction): Promise<void>;
    private handlePauseResume;
    private handleLoop;
    private handleShuffle;
    private handleQueueNavigation;
    private updateQueueDisplay;
}
//# sourceMappingURL=ButtonHandler.d.ts.map