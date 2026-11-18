import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

# 1. Prepare kidobits_wallet.js
wallet_content = """/**
 * Kidobits Platform - Unified Wallet, Progression & Gamification Engine
 * Handles Stars (Leaderboard), Coins (Shop), Streak, Badges & Continue Lesson.
 * Synchronizes with Kidobits Backend API (/kidobits/api/progress/*).
 */
(function() {
  const STORAGE_KEY = 'kidobits_profile_v1';
  const API_BASE = '/kidobits/api';

  const DEFAULT_USER = {
    userId: 'guest',
    name: 'น้องเอ็มม่า',
    avatar: '👧',
    avatarHat: '',
    stars: 1240,
    coins: 350,
    streak: 7,
    lastActiveDate: new Date().toISOString().split('T')[0],
    completedLessons: ['L1.01'],
    lastLesson: {
      subject: 'Phonics',
      subjectIcon: '🔤',
      lessonId: 'L1.01',
      title: 'Level 1: -at family',
      url: 'theme_phonicsLesson.html?lesson=L1.01',
      stars: 3,
      step: 1,
      totalSteps: 5,
      percent: 20,
      done: false,
      updatedAt: new Date().toISOString()
    },
    inventory: ['hat_starry'],
    unlockedBadges: ['first_word', 'streak_7']
  };

  const KidobitsWallet = {
    getUser() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          return Object.assign({}, DEFAULT_USER, parsed);
        }
      } catch (e) {
        console.warn('KidobitsWallet: Error reading localStorage', e);
      }
      this.saveUser(DEFAULT_USER);
      return Object.assign({}, DEFAULT_USER);
    },

    saveUser(user) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
        window.dispatchEvent(new CustomEvent('kidobits_wallet_updated', { detail: user }));
      } catch (e) {
        console.error('KidobitsWallet: Error writing localStorage', e);
      }
    },

    addReward(starsEarned = 10, coinsEarned = 20, lessonMeta = null) {
      const user = this.getUser();
      user.stars = (Number(user.stars) || 0) + Number(starsEarned);
      user.coins = (Number(user.coins) || 0) + Number(coinsEarned);

      // Check daily streak
      const today = new Date().toISOString().split('T')[0];
      if (user.lastActiveDate !== today) {
        user.streak = (Number(user.streak) || 0) + 1;
        user.lastActiveDate = today;
      }

      if (lessonMeta && lessonMeta.lessonId) {
        user.completedLessons = user.completedLessons || [];
        if (!user.completedLessons.includes(lessonMeta.lessonId)) {
          user.completedLessons.push(lessonMeta.lessonId);
        }
        user.lastLesson = {
          subject: lessonMeta.subject || 'Phonics',
          subjectIcon: lessonMeta.subjectIcon || '🔤',
          lessonId: lessonMeta.lessonId,
          title: lessonMeta.title || lessonMeta.lessonId,
          url: lessonMeta.url || `theme_phonicsLesson.html?lesson=${lessonMeta.lessonId}`,
          stars: lessonMeta.stars || 3,
          step: lessonMeta.step || 5,
          totalSteps: lessonMeta.totalSteps || 5,
          percent: 100,
          done: true,
          updatedAt: new Date().toISOString()
        };
        // Also sync completion to API
        this.saveProgress({
          ...lessonMeta,
          step: 5,
          totalSteps: 5,
          done: true,
          percent: 100
        });
      }

      this.saveUser(user);
      return user;
    },

    setLastLesson(lessonMeta) {
      const user = this.getUser();
      const step = lessonMeta.step || 1;
      const totalSteps = lessonMeta.totalSteps || 5;
      const done = Boolean(lessonMeta.done);
      const percent = done ? 100 : Math.min(99, Math.max(5, Math.round((step / totalSteps) * 100)));

      user.lastLesson = {
        subject: lessonMeta.subject || 'Phonics',
        subjectIcon: lessonMeta.subjectIcon || '🔤',
        lessonId: lessonMeta.lessonId,
        title: lessonMeta.title || lessonMeta.lessonId,
        url: lessonMeta.url || `theme_phonicsLesson.html?lesson=${lessonMeta.lessonId}&step=${step}`,
        stars: lessonMeta.stars || 3,
        step: step,
        totalSteps: totalSteps,
        percent: percent,
        done: done,
        updatedAt: new Date().toISOString()
      };
      this.saveUser(user);
      return user;
    },

    // -------------------------------------------------------------
    // Progress API Integration (Continue Lesson System)
    // -------------------------------------------------------------
    async saveProgress(lessonMeta) {
      if (!lessonMeta || !lessonMeta.lessonId) return null;
      this.setLastLesson(lessonMeta);

      const user = this.getUser();
      const payload = {
        user_id: user.userId || 'guest',
        subject: lessonMeta.subject || 'Phonics',
        lesson_id: lessonMeta.lessonId,
        level: lessonMeta.level || null,
        step: lessonMeta.step || 1,
        item_index: lessonMeta.itemIndex || lessonMeta.index || 0,
        total_steps: lessonMeta.totalSteps || 5,
        done: Boolean(lessonMeta.done),
        title: lessonMeta.title || '',
        url: lessonMeta.url || `theme_phonicsLesson.html?lesson=${lessonMeta.lessonId}&step=${lessonMeta.step || 1}`
      };

      try {
        const res = await fetch(`${API_BASE}/progress/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        return data;
      } catch (err) {
        console.warn('KidobitsWallet: Failed to sync progress to API', err);
        return null;
      }
    },

    async fetchLatestProgress(userId = 'guest', subject = '') {
      try {
        let url = `${API_BASE}/progress/latest?user_id=${encodeURIComponent(userId)}`;
        if (subject) url += `&subject=${encodeURIComponent(subject)}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data && data.ok && data.has_progress && data.latest) {
          const l = data.latest;
          const user = this.getUser();
          user.lastLesson = {
            subject: l.subject || 'Phonics',
            subjectIcon: '🔤',
            lessonId: l.lesson_id,
            title: l.title,
            url: l.url,
            step: l.step,
            totalSteps: l.total_steps || 5,
            percent: l.percent,
            done: l.done,
            nextLessonId: l.next_lesson_id,
            updatedAt: new Date(l.updated_at * 1000).toISOString()
          };
          this.saveUser(user);
          return user.lastLesson;
        }
      } catch (err) {
        console.warn('KidobitsWallet: Failed to fetch latest progress from API', err);
      }
      return this.getUser().lastLesson;
    },

    async getAllProgress(userId = 'guest') {
      try {
        const res = await fetch(`${API_BASE}/progress/all?user_id=${encodeURIComponent(userId)}`);
        return await res.json();
      } catch (err) {
        console.warn('KidobitsWallet: Failed to fetch all progress', err);
        return null;
      }
    },

    buyItem(itemId, priceInCoins, itemType = 'hat') {
      const user = this.getUser();
      priceInCoins = Number(priceInCoins) || 0;
      if (user.coins < priceInCoins) {
        return { success: false, reason: 'not_enough_coins' };
      }
      user.coins -= priceInCoins;
      user.inventory = user.inventory || [];
      if (!user.inventory.includes(itemId)) {
        user.inventory.push(itemId);
      }
      if (itemType === 'hat') {
        user.avatarHat = itemId;
      }
      this.saveUser(user);
      return { success: true, user };
    },

    getLeaderboard() {
      const user = this.getUser();
      const peers = [
        { id: 'p1', name: 'Leo', avatar: '🦁', stars: 1280, isUser: false },
        { id: 'p2', name: 'Emma', avatar: '🐱', stars: 1150, isUser: false },
        { id: 'p3', name: 'Noah', avatar: '🐶', stars: 980, isUser: false },
        { id: 'p4', name: 'Mia', avatar: '🐰', stars: 920, isUser: false },
        { id: 'p5', name: 'Liam', avatar: '🦊', stars: 850, isUser: false },
        { id: 'p6', name: 'Lucas', avatar: '🐼', stars: 740, isUser: false },
        { id: 'p7', name: 'Sophia', avatar: '🦄', stars: 620, isUser: false },
        { id: 'p8', name: 'Oliver', avatar: '🦊', stars: 550, isUser: false }
      ];

      const currentHero = {
        id: 'me',
        name: `${user.name} (คุณ)`,
        avatar: user.avatar,
        avatarHat: user.avatarHat,
        stars: user.stars,
        isUser: true
      };

      const ranking = [...peers, currentHero].sort((a, b) => b.stars - a.stars);
      const userIndex = ranking.findIndex(p => p.isUser);
      const userRank = userIndex + 1;

      return {
        ranking,
        userRank,
        userStars: user.stars,
        userCoins: user.coins,
        top3: ranking.slice(0, 3)
      };
    }
  };

  window.KidobitsWallet = KidobitsWallet;
})();
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/kidobits_wallet.js', 'w') as f:
    f.write(wallet_content)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S cp /tmp/kidobits_wallet.js /var/www/kidobits/js/kidobits_wallet.js && echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/js/kidobits_wallet.js")
print("Copy wallet stdout:", stdout.read().decode())
print("Copy wallet stderr:", stderr.read().decode())

ssh.close()
