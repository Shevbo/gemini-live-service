/**
 * Добавляет проект gemini-live-service на Shectory Portal.
 * Запускать из директории shectory-portal:
 *   cd /home/shectory/workspaces/shectory-portal
 *   node ../gemini-live-service/scripts/add-to-portal.js
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const existing = await prisma.project.findUnique({ where: { slug: 'gemini-live-service' } });
  if (existing) {
    console.log('Проект уже существует:', existing.id);
    return;
  }

  const project = await prisma.project.create({
    data: {
      slug: 'gemini-live-service',
      name: 'Медсестра — голосовой ассистент',
      description:
        'Голосовой терапевтический ассистент на базе Gemini Live API. ' +
        'Bidirectional аудио без ограничений, дневник настроения, учёт расходов. ' +
        'Данные хранятся для использования с живым терапевтом.',
      version: '1.0.0',
      techStack: {
        create: [
          { name: 'Python', sortOrder: 1 },
          { name: 'FastAPI', sortOrder: 2 },
          { name: 'Gemini Live API', sortOrder: 3 },
          { name: 'PostgreSQL', sortOrder: 4 },
          { name: 'Redis', sortOrder: 5 },
          { name: 'Prisma', sortOrder: 6 },
          { name: 'Docker', sortOrder: 7 },
        ],
      },
    },
  });

  console.log('Проект добавлен на портал:', project.id, project.slug);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
