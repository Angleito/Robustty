import { Track } from './types';

export class QueueManager {
  private queue: Track[] = [];
  private currentIndex: number = -1;
  private loop: 'none' | 'track' | 'queue' = 'none';

  async add(track: Track) {
    this.queue.push(track);
  }

  async getNext(): Promise<Track | null> {
    if (this.loop === 'track' && this.currentIndex >= 0) {
      return this.queue[this.currentIndex];
    }

    this.currentIndex++;
    
    if (this.currentIndex >= this.queue.length) {
      if (this.loop === 'queue') {
        this.currentIndex = 0;
      } else {
        return null;
      }
    }

    return this.queue[this.currentIndex] || null;
  }

  getCurrent(): Track | null {
    return this.queue[this.currentIndex] || null;
  }

  getQueue(): Track[] {
    return this.queue.slice(this.currentIndex + 1);
  }

  clear() {
    this.queue = [];
    this.currentIndex = -1;
  }

  setLoop(mode: 'none' | 'track' | 'queue') {
    this.loop = mode;
  }

  getLoopMode(): 'none' | 'track' | 'queue' {
    return this.loop;
  }

  remove(index: number): boolean {
    if (index < 0 || index >= this.queue.length) return false;
    
    this.queue.splice(index, 1);
    
    if (index <= this.currentIndex && this.currentIndex > 0) {
      this.currentIndex--;
    }
    
    return true;
  }

  shuffle() {
    const upcoming = this.queue.slice(this.currentIndex + 1);
    
    for (let i = upcoming.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [upcoming[i], upcoming[j]] = [upcoming[j], upcoming[i]];
    }
    
    this.queue = [
      ...this.queue.slice(0, this.currentIndex + 1),
      ...upcoming
    ];
  }
}