import { 
  EmbedBuilder, 
  ActionRowBuilder, 
  ButtonBuilder, 
  ButtonStyle,
  MessageActionRowComponentBuilder,
  ButtonInteraction
} from 'discord.js';
import { YouTubeVideo, SearchSession } from '../domain/types';
import { RedisClient } from './RedisClient';
import { logger } from './logger';

export class SearchResultHandler {
  private redis: RedisClient;
  private readonly SESSION_TTL = 30; // 30 seconds

  constructor(redis: RedisClient) {
    this.redis = redis;
  }

  async createSearchSession(
    userId: string,
    guildId: string,
    query: string,
    results: YouTubeVideo[]
  ): Promise<string> {
    const sessionId = `search_${userId}_${Date.now()}`;
    const session: SearchSession = {
      sessionId,
      userId,
      guildId,
      query,
      results: results.slice(0, 5), // Limit to 5 results
      createdAt: Date.now(),
      expiresAt: Date.now() + (this.SESSION_TTL * 1000)
    };

    await this.redis.set(
      `search:session:${sessionId}`,
      JSON.stringify(session),
      this.SESSION_TTL
    );

    logger.info(`Created search session ${sessionId} for user ${userId}`);
    return sessionId;
  }

  async getSearchSession(sessionId: string): Promise<SearchSession | null> {
    const sessionData = await this.redis.get(`search:session:${sessionId}`);
    if (!sessionData) {
      return null;
    }

    try {
      return JSON.parse(sessionData);
    } catch (error) {
      logger.error('Failed to parse search session:', error);
      return null;
    }
  }

  async deleteSearchSession(sessionId: string): Promise<void> {
    await this.redis.del(`search:session:${sessionId}`);
    logger.info(`Deleted search session ${sessionId}`);
  }

  createSearchEmbed(query: string, results: YouTubeVideo[]): EmbedBuilder {
    const embed = new EmbedBuilder()
      .setTitle('🔍 Search Results')
      .setDescription(`Results for: **${query}**`)
      .setColor(0x3498db)
      .setTimestamp();

    results.forEach((video, index) => {
      const duration = this.formatDuration(video.duration);
      embed.addFields({
        name: `${index + 1}. ${video.title}`,
        value: `**Channel:** ${video.channel}\n**Duration:** ${duration}\n[Watch on YouTube](${video.url})`,
        inline: false
      });
    });

    embed.setFooter({ 
      text: 'Select a song using the buttons below • Session expires in 30s' 
    });

    return embed;
  }

  createSelectionButtons(sessionId: string, resultCount: number): ActionRowBuilder<MessageActionRowComponentBuilder> {
    const row = new ActionRowBuilder<MessageActionRowComponentBuilder>();
    
    // Limit to 4 number buttons to leave room for cancel button (Discord max is 5 per row)
    const buttonCount = Math.min(resultCount, 4);
    const numberEmojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣'];

    for (let i = 0; i < buttonCount; i++) {
      row.addComponents(
        new ButtonBuilder()
          .setCustomId(`search_select_${sessionId}_${i}`)
          .setLabel(`${i + 1}`)
          .setEmoji(numberEmojis[i])
          .setStyle(ButtonStyle.Primary)
      );
    }

    // Add cancel button
    row.addComponents(
      new ButtonBuilder()
        .setCustomId(`search_cancel_${sessionId}`)
        .setLabel('Cancel')
        .setEmoji('❌')
        .setStyle(ButtonStyle.Secondary)
    );

    return row;
  }

  async handleSearchSelection(interaction: ButtonInteraction): Promise<YouTubeVideo | null> {
    const customId = interaction.customId;
    
    if (!customId.startsWith('search_')) {
      return null;
    }

    const parts = customId.split('_');
    if (parts.length < 3) {
      return null;
    }

    const action = parts[1]; // 'select' or 'cancel'
    const sessionId = parts[2];

    // Handle cancel
    if (action === 'cancel') {
      await this.deleteSearchSession(sessionId);
      await interaction.update({
        content: '❌ Search cancelled.',
        embeds: [],
        components: []
      });
      return null;
    }

    // Handle selection
    if (action === 'select' && parts.length >= 4) {
      const selectedIndex = parseInt(parts[3]);
      
      const session = await this.getSearchSession(sessionId);
      if (!session) {
        await interaction.update({
          content: '⏰ Search session expired. Please search again.',
          embeds: [],
          components: []
        });
        return null;
      }

      // Verify user ownership
      if (session.userId !== interaction.user.id) {
        await interaction.reply({
          content: '❌ You can only select from your own search results.',
          ephemeral: true
        });
        return null;
      }

      const selectedVideo = session.results[selectedIndex];
      if (!selectedVideo) {
        await interaction.update({
          content: '❌ Invalid selection.',
          embeds: [],
          components: []
        });
        return null;
      }

      // Clean up session
      await this.deleteSearchSession(sessionId);

      // Update message to show selection
      await interaction.update({
        content: `✅ Selected: **${selectedVideo.title}**`,
        embeds: [],
        components: []
      });

      logger.info(`User ${interaction.user.id} selected video ${selectedVideo.id} from search`);
      return selectedVideo;
    }

    return null;
  }

  async isSessionExpired(sessionId: string): Promise<boolean> {
    const exists = await this.redis.exists(`search:session:${sessionId}`);
    return !exists;
  }

  async cleanupExpiredSessions(): Promise<void> {
    // This would be called periodically to clean up any leftover sessions
    // Redis TTL should handle most cleanup automatically
    logger.info('Cleaned up expired search sessions');
  }

  private formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
}