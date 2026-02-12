// server.js - WebRTC Signaling Server для Cinema Party
// Основан на лучших практиках из [citation:3][citation:7]

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const path = require('path');
require('dotenv').config();

const app = express();
const server = http.createServer(app);

// Настройка CORS для работы с Telegram ботом и веб-плеером
const io = new Server(server, {
  cors: {
    origin: '*', // В продакшене заменить на конкретные домены
    methods: ['GET', 'POST'],
    credentials: true
  },
  connectionStateRecovery: {
    // Автоматическое восстановление при обрыве
    maxDisconnectionDuration: 120000 // 2 минуты
  }
});

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ============ ХРАНИЛИЩЕ КОМНАТ ============
// Используем Map для быстрого доступа
const rooms = new Map();

// ============ СИГНАЛЬНЫЙ СЕРВЕР ============
io.on('connection', (socket) => {
  console.log(`🔌 Peer connected: ${socket.id}`);

  // --- УПРАВЛЕНИЕ КОМНАТАМИ ---
  socket.on('join-room', ({ roomId, userId, username }) => {
    // Покидаем предыдущую комнату, если была
    if (socket.roomId) {
      socket.leave(socket.roomId);
      removeUserFromRoom(socket.roomId, socket.id);
    }

    socket.join(roomId);
    socket.roomId = roomId;
    socket.userId = userId;
    socket.username = username || `User-${socket.id.slice(0, 4)}`;

    // Инициализируем комнату, если её нет
    if (!rooms.has(roomId)) {
      rooms.set(roomId, new Map());
    }

    const roomPeers = rooms.get(roomId);
    roomPeers.set(socket.id, {
      id: socket.id,
      userId: socket.userId,
      username: socket.username,
      joinedAt: Date.now()
    });

    console.log(`👥 ${socket.username} (${socket.userId}) joined room ${roomId}`);

    // Отправляем новому участнику список текущих пиров
    const existingPeers = Array.from(roomPeers.entries())
      .filter(([id]) => id !== socket.id)
      .map(([id, data]) => ({ id, userId: data.userId, username: data.username }));

    socket.emit('room-state', {
      peers: existingPeers,
      hostId: findHost(roomId)?.id || socket.id,
      videoState: roomPeers.get('videoState') || null
    });

    // Уведомляем остальных о новом участнике
    socket.to(roomId).emit('peer-joined', {
      id: socket.id,
      userId: socket.userId,
      username: socket.username
    });
  });

  // --- ВЫДЕЛЕНИЕ ХОСТА (первый вошедший) ---
  function findHost(roomId) {
    const roomPeers = rooms.get(roomId);
    if (!roomPeers || roomPeers.size === 0) return null;
    // Первый подключившийся становится хостом
    const firstPeer = Array.from(roomPeers.entries())[0];
    return firstPeer ? { id: firstPeer[0], data: firstPeer[1] } : null;
  }

  // --- УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ ИЗ КОМНАТЫ ---
  function removeUserFromRoom(roomId, socketId) {
    const roomPeers = rooms.get(roomId);
    if (roomPeers) {
      roomPeers.delete(socketId);
      if (roomPeers.size === 0) {
        rooms.delete(roomId);
        console.log(`🚪 Room ${roomId} deleted (empty)`);
      } else {
        socket.to(roomId).emit('peer-left', socketId);
      }
    }
  }

  // --- WEBRTC СИГНАЛИЗАЦИЯ (ключевая часть) ---

  // Предложение соединения (offer)
  socket.on('offer', ({ target, offer }) => {
    console.log(`📤 Offer from ${socket.id} to ${target}`);
    socket.to(target).emit('offer', {
      offer,
      sender: socket.id
    });
  });

  // Ответ на предложение (answer)
  socket.on('answer', ({ target, answer }) => {
    console.log(`📥 Answer from ${socket.id} to ${target}`);
    socket.to(target).emit('answer', {
      answer,
      sender: socket.id
    });
  });

  // ICE-кандидаты (сетевые пути)
  socket.on('ice-candidate', ({ target, candidate }) => {
    socket.to(target).emit('ice-candidate', {
      candidate,
      sender: socket.id
    });
  });

  // --- СИНХРОНИЗАЦИЯ ВИДЕО (PAUSE/PLAY/SEEK) ---
  socket.on('video-action', ({ roomId, action, time, url }) => {
    console.log(`🎬 Video ${action} in ${roomId} at ${time}s`);

    // Сохраняем состояние видео в комнате
    const roomPeers = rooms.get(roomId);
    if (roomPeers) {
      const videoState = roomPeers.get('videoState') || {};
      videoState[action] = { time, url, userId: socket.userId, timestamp: Date.now() };
      roomPeers.set('videoState', videoState);
    }

    // Рассылаем всем КРОМЕ отправителя
    socket.to(roomId).emit('video-sync', {
      userId: socket.userId,
      action,
      time,
      url
    });
  });

  // --- ЗАГРУЗКА НОВОГО ВИДЕО В КОМНАТУ ---
  socket.on('video-load', ({ roomId, videoUrl }) => {
    console.log(`📺 Video loaded in ${roomId}: ${videoUrl}`);

    const roomPeers = rooms.get(roomId);
    if (roomPeers) {
      roomPeers.set('videoState', { url: videoUrl, time: 0, playing: false });
    }

    socket.to(roomId).emit('video-loaded', {
      url: videoUrl,
      userId: socket.userId
    });
  });

  // --- ЧАТ В КОМНАТЕ (опционально) ---
  socket.on('chat-message', ({ roomId, message }) => {
    io.to(roomId).emit('chat-message', {
      userId: socket.userId,
      username: socket.username,
      message,
      timestamp: Date.now()
    });
  });

  // --- ОТКЛЮЧЕНИЕ ---
  socket.on('disconnect', () => {
    console.log(`🔌 Peer disconnected: ${socket.id}`);
    if (socket.roomId) {
      removeUserFromRoom(socket.roomId, socket.id);
    }
  });
});

// ============ HTTP ЭНДПОИНТЫ ============
app.get('/', (req, res) => {
  res.json({
    status: 'online',
    service: 'Cinema Party WebRTC Signaling Server',
    timestamp: new Date().toISOString(),
    rooms: rooms.size,
    peers: Array.from(rooms.values()).reduce((acc, room) => acc + room.size, 0)
  });
});

app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

app.get('/room/:roomId', (req, res) => {
  const roomId = req.params.roomId;
  const roomPeers = rooms.get(roomId);

  if (!roomPeers) {
    return res.status(404).json({ error: 'Room not found' });
  }

  const peers = Array.from(roomPeers.entries())
    .filter(([id]) => id !== 'videoState')
    .map(([id, data]) => ({
      id,
      userId: data.userId,
      username: data.username
    }));

  res.json({
    roomId,
    peers,
    host: findHost(roomId)?.id,
    videoState: roomPeers.get('videoState') || null
  });
});

// ============ ЗАПУСК СЕРВЕРА ============
const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`
╔════════════════════════════════════════╗
║   🎬 Cinema Party WebRTC Signaling    ║
╠════════════════════════════════════════╣
║  Server:     http://localhost:${PORT}      ║
║  WebSocket:  ws://localhost:${PORT}        ║
║  Rooms:      0                         ║
║  Status:     ONLINE                   ║
╚════════════════════════════════════════╝
  `);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, closing server...');
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});