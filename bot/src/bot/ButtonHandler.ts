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

  createSelectionButtons(): ActionRowBuilder<MessageActionRowComponentBuilder> {
    return new ActionRowBuilder<MessageActionRowComponentBuilder>()
      .addComponents(
        new ButtonBuilder()
          .setCustomId('select_1')
          .setLabel('1')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('select_2')
          .setLabel('2')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('select_3')
          .setLabel('3')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('select_4')
          .setLabel('4')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId('select_5')
          .setLabel('5')
          .setStyle(ButtonStyle.Primary)
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
      const customId = interaction.customId;

      // Handle search-related buttons first (these have different interaction patterns)
      if (customId.startsWith('search_')) {
        await this.handleSearchSelection(interaction);
        return;
      }

      // For all other buttons, defer update first
      await interaction.deferUpdate();

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
          } else if (customId.startsWith('select_')) {
            await this.handleSimpleSelection(interaction, customId);
          }
      }
    } catch (error) {
      logger.error(`Button error (${interaction.customId}):`, error);
      
      // Try to respond if we haven't already
      try {
        if (interaction.deferred) {
          await interaction.editReply({ 
            content: 'An error occurred while processing the button click' 
          });
        } else {
          await interaction.reply({ 
            content: 'An error occurred while processing the button click',
            ephemeral: true
          });
        }
      } catch (responseError) {
        logger.error('Failed to send error response:', responseError);
      }
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

  private async handleSimpleSelection(interaction: ButtonInteraction, customId: string) {
    // This handles simple numbered selections (select_1, select_2, etc.)
    // Used for basic search results without session management
    await interaction.editReply({ 
      content: 'Simple selection functionality not implemented. Please use the search command with proper search results.',
      components: []
    });
  }

  private async handleSearchSelection(interaction: ButtonInteraction) {
    try {
      // Let SearchResultHandler handle the button interaction and get the selected video
      const searchHandler = this.bot.getSearchResultHandler();
      const selectedVideo = await searchHandler.handleSearchSelection(interaction);
      
      if (!selectedVideo) {
        // SearchResultHandler already handled the interaction (cancel, error, etc.)
        return;
      }

      // Now add the selected video to queue and start playback
      if (!interaction.guildId) {
        await interaction.followUp({ 
          content: 'This can only be used in a server!',
          ephemeral: true
        });
        return;
      }

      const result = await this.bot.playSelectedVideoFromButton(
        selectedVideo, 
        interaction.guildId, 
        interaction.user.id
      );

      await interaction.followUp({ 
        content: result.message,
        ephemeral: !result.success
      });

    } catch (error) {
      logger.error('Search selection error:', error);
      
      try {
        await interaction.followUp({ 
          content: 'An error occurred while processing your selection',
          ephemeral: true
        });
      } catch (followUpError) {
        logger.error('Failed to send error response:', followUpError);
      }
    }
  }
}