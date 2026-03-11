"""
Скрипт для просмотра всех пользователей и их последней активности.
Запуск: python check_users.py
"""
import asyncio
import asyncpg
from datetime import datetime

DB_CONFIG = {
    "host": "dpg-d4lr6ore5dus73fv0mtg-a.frankfurt-postgres.render.com",
    "port": 5432,
    "database": "twelvesteps_db",
    "user": "twelvesteps_db_user",
    "password": "WALT3o3sIG7q6BPeijZZQmdA7AJ2E3Nn"
}


async def main():
    conn = await asyncpg.connect(**DB_CONFIG)

    # Все пользователи + сводная статистика
    rows = await conn.fetch("""
        SELECT
            u.id,
            u.telegram_id,
            u.username,
            u.first_name,
            u.display_name,
            u.user_role,
            u.last_active,
            u.created_at,
            (SELECT COUNT(*) FROM messages WHERE user_id = u.id) AS msg_count,
            (SELECT MAX(created_at) FROM messages WHERE user_id = u.id) AS last_message_at,
            (SELECT COUNT(*) FROM frames WHERE user_id = u.id) AS frame_count,
            (SELECT COUNT(*) FROM step_answers WHERE user_id = u.id) AS step_answers_count,
            (SELECT COUNT(*) FROM gratitudes WHERE user_id = u.id) AS gratitude_count,
            (SELECT COUNT(*) FROM profile_section_data WHERE user_id = u.id) AS profile_entries
        FROM users u
        ORDER BY u.last_active DESC NULLS LAST
    """)

    print(f"\n{'='*80}")
    print(f"  ПОЛЬЗОВАТЕЛИ GPT-SELF — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Всего: {len(rows)}")
    print(f"{'='*80}\n")

    for r in rows:
        name = r["first_name"] or r["username"] or r["telegram_id"]
        print(f"┌─ {name} (ID={r['id']}, TG={r['telegram_id']})")
        print(f"│  username: @{r['username'] or '—'}  |  role: {r['user_role'] or '—'}")
        print(f"│  Создан: {r['created_at']}")
        print(f"│  last_active: {r['last_active'] or 'никогда'}")
        print(f"│  Последнее сообщение: {r['last_message_at'] or 'нет'}")
        print(f"│  Сообщений: {r['msg_count']}  |  Фреймов: {r['frame_count']}")
        print(f"│  Ответов на шаги: {r['step_answers_count']}  |  Благодарностей: {r['gratitude_count']}")
        print(f"│  Записей профиля: {r['profile_entries']}")
        print(f"└{'─'*60}\n")

    # Последние 5 сообщений по всем юзерам
    recent = await conn.fetch("""
        SELECT m.created_at, m.sender_role, m.content, u.first_name, u.username
        FROM messages m
        JOIN users u ON u.id = m.user_id
        ORDER BY m.created_at DESC
        LIMIT 10
    """)

    if recent:
        print(f"\n{'='*80}")
        print(f"  ПОСЛЕДНИЕ 10 СООБЩЕНИЙ (все юзеры)")
        print(f"{'='*80}\n")
        for m in recent:
            who = m["first_name"] or m["username"] or "?"
            preview = (m["content"] or "")[:100].replace("\n", " ")
            print(f"  {m['created_at']}  [{m['sender_role']}]  {who}: {preview}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
