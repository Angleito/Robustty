import { 
  ButtonInteraction, 
  ActionRowBuilder, 
  ButtonBuilder, 
  ButtonStyle,
  MessageActionRowComponentBuilder
} from 'discord.js';
import { MusicBot } from './MusicBot';
import { logger } from '../services/logger';

export class ButtonHandler {
  private bot: MusicBot;

  constructor(bot: MusicBot) {
    this.bot = bot;
  }

  createPlayerControls(): ActionRowBuilder<MessageActionRowComponentBuilder> {
    return new ActionRowBuilder<MessageActionRowComponentBuilder>()
      .addComponents(
        new ButtonBuilder()
          .setCustomId('pause_resume')
          .setLabel('⏯️')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('skip')
          .setLabel('⏭️')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('stop')
          .setLabel('⏹️')
          .setStyle(ButtonStyle.Danger),
        new ButtonBuilder()
          .setCustomId('loop')
          .setLabel('🔁')
          .setStyle(ButtonStyle.Secondary),
        new ButtonBuilder()
          .setCustomId('shuffle')
          .setLabel('🔀')
          .setStyle(ButtonStyle.Secondary)
      );
  }

  createQueueControls(page: number, totalPages: number): ActionRowBuilder<MessageActionRowComponentBuilder> {
    return new ActionRowBuilder<MessageActionRowComponentBuilder>()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(`queue_first`)
          .setLabel('⏮️')
          .setStyle(ButtonStyle.Secondary)
          .setDisabled(page === 1),
        new ButtonBuilder()
          .setCustomId(`queue_prev_${page}`)
          .setLabel('◀️')
          .setStyle(ButtonStyle.Secondary)
          .setDisabled(page === 1),
        new ButtonBuilder()
          .setCustomId(`queue_page`)
          .setLabel(`${page}/${totalPages}`)
          .setStyle(ButtonStyle.Secondary)
          .setDisabled(true),
        new ButtonBuilder()
          .setCustomId(`queue_next_${page}`)
          .setLabel('▶️')
          .setStyle(ButtonStyle.Secondary)
          .setDisabled(page === totalPages),
        new ButtonBuilder()
          .setCustomId(`queue_last`)
          .setLabel('⏭️')
          .setStyle(ButtonStyle.Secondary)
          .setDisabled(page === totalPages)
      );
  }

  async handleButton(interaction: ButtonInteraction) {
    if (!interaction.isButton()) return;

    try {
      await interaction.deferUpdate();

      const customId = interaction.customId;

      switch (customId) {
        case 'pause_resume':
          await this.handlePauseResume(interaction);
          break;
        
        case 'skip':
          if (!interaction.guildId) {
            await interaction.editReply({ content: 'This button can only be used in a server!' });
            break;
          }
          await this.bot.skip(interaction.guildId);
          await interaction.editReply({ content: 'Skipped to next song! ⏭️' });
          break;
        
        case 'stop':
          if (!interaction.guildId) {
            await interaction.editReply({ content: 'This button can only be used in a server!' });
            break;
          }
          await this.bot.stop(interaction.guildId);
          await interaction.editReply({ 
            content: 'Stopped playback and cleared queue! ⏹️',
            components: []
          });
          break;
        
        case 'loop':
          await this.handleLoop(interaction);
          break;
        
        case 'shuffle':
          await this.handleShuffle(interaction);
          break;
        
        default:
          if (customId.startsWith('queue_')) {
            await this.handleQueueNavigation(interaction, customId);
          }
      }
    } catch (error) {
      logger.error(`Button error (${interaction.customId}):`, error);
      await interaction.editReply({ 
        content: 'An error occurred while processing the button click' 
      });
    }
  }

  private async handlePauseResume(interaction: ButtonInteraction) {
    // This would need implementation in VoiceManager
    await interaction.editReply({ content: 'Pause/Resume functionality coming soon!' });
  }

  private async handleLoop(interaction: ButtonInteraction) {
    const queue = this.bot.getQueueManager();
    const currentLoop = queue.getLoopMode();
    
    let newLoop: 'none' | 'track' | 'queue';
    let message: string;
    
    switch (currentLoop) {
      case 'none':
        newLoop = 'track';
        message = 'Now looping current track! 🔂';
        break;
      case 'track':
        newLoop = 'queue';
        message = 'Now looping entire queue! 🔁';
        break;
      case 'queue':
        newLoop = 'none';
        message = 'Loop disabled! ▶️';
        break;
    }
    
    queue.setLoop(newLoop);
    await interaction.editReply({ content: message });
  }

  private async handleShuffle(interaction: ButtonInteraction) {
    this.bot.getQueueManager().shuffle();
    await interaction.editReply({ content: 'Queue shuffled! 🔀' });
  }

  private async handleQueueNavigation(interaction: ButtonInteraction, customId: string) {
    const parts = customId.split('_');
    const action = parts[1];
    const currentPage = parts[2] ? parseInt(parts[2]) : 1;
    
    let newPage = currentPage;
    
    switch (action) {
      case 'first':
        newPage = 1;
        break;
      case 'prev':
        newPage = Math.max(1, currentPage - 1);
        break;
      case 'next':
        newPage = currentPage + 1;
        break;
      case 'last':
        // This would need to be calculated based on queue size
        break;
    }
    
    // Update the queue display with new page
    await this.updateQueueDisplay(interaction, newPage);
  }

  private async updateQueueDisplay(interaction: ButtonInteraction, page: number) {
    const queue = this.bot.getQueueManager().getQueue();
    const itemsPerPage = 10;
    const totalPages = Math.ceil(queue.length / itemsPerPage);
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    
    const embed = {
      title: 'Music Queue',
      description: queue.slice(start, end).map((track, index) => 
        `${start + index + 1}. **${track.title}** - <@${track.requestedBy}>`
      ).join('\n') || 'Queue is empty',
      footer: { text: `Page ${page}/${totalPages} • Total: ${queue.length} songs` }
    };
    
    await interaction.editReply({ 
      embeds: [embed],
      components: [this.createQueueControls(page, totalPages)]
    });
  }
}