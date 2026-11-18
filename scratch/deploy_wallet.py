import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

wallet_code = '''/**
 * Kidobits Platform - Unified Wallet, Progression & Gamification Engine
 * Handles Stars (Leaderboard), Coins (Shop), Streak, Badges & Continue Lesson.
 */
(function() {
  const STORAGE_KEY = 'kidobits_profile_v1';

  const DEFAULT_USER = {
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
      step: 5,
      totalSteps: 5,
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
          updatedAt: new Date().toISOString()
        };
      }

      this.saveUser(user);
      return user;
    },

    setLastLesson(lessonMeta) {
      const user = this.getUser();
      user.lastLesson = {
        subject: lessonMeta.subject || 'Phonics',
        subjectIcon: lessonMeta.subjectIcon || '🔤',
        lessonId: lessonMeta.lessonId,
        title: lessonMeta.title || lessonMeta.lessonId,
        url: lessonMeta.url || `theme_phonicsLesson.html?lesson=${lessonMeta.lessonId}`,
        stars: lessonMeta.stars || 3,
        step: lessonMeta.step || 1,
        totalSteps: lessonMeta.totalSteps || 5,
        updatedAt: new Date().toISOString()
      };
      this.saveUser(user);
      return user;
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
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/kidobits_wallet.js', 'w') as f:
    f.write(wallet_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S mv /tmp/kidobits_wallet.js /var/www/kidobits/js/kidobits_wallet.js && echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/js/kidobits_wallet.js")
print(stdout.read().decode('utf-8'))
print("Successfully deployed /var/www/kidobits/js/kidobits_wallet.js")

ssh.close()
