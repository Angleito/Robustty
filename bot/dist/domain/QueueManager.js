"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.QueueManager = void 0;
class QueueManager {
    queue = [];
    currentIndex = -1;
    loop = 'none';
    async add(track) {
        this.queue.push(track);
    }
    async getNext() {
        if (this.loop === 'track' && this.currentIndex >= 0) {
            return this.queue[this.currentIndex];
        }
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            if (this.loop === 'queue') {
                this.currentIndex = 0;
            }
            else {
                return null;
            }
        }
        return this.queue[this.currentIndex] || null;
    }
    getCurrent() {
        return this.queue[this.currentIndex] || null;
    }
    getQueue() {
        return this.queue.slice(this.currentIndex + 1);
    }
    clear() {
        this.queue = [];
        this.currentIndex = -1;
    }
    setLoop(mode) {
        this.loop = mode;
    }
    getLoopMode() {
        return this.loop;
    }
    remove(index) {
        if (index < 0 || index >= this.queue.length)
            return false;
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
exports.QueueManager = QueueManager;
//# sourceMappingURL=QueueManager.js.map