# twelvesteps/services/personalization_service.py (фрагмент изменений)
async def update_personalized_prompt_from_all_answers(self, user_id: int):
    # ... существующий код для онбординга/профиля/чата

    # Добавь обновление из шагов
    step_answers = await self.repo.get_step_answers(user_id)  # из repo
    prompt += "\n=== ОТВЕТЫ ПО ШАГАМ ===\n"
    for answer in step_answers:
        prompt += f"[Шаг {answer.step_id}] Вопрос: {answer.question_text}\nОтвет: {answer.answer}\n"

    # После обновления — классификация памяти (Volatile/Dynamic/Stable)
    await self.classify_memory(user_id, prompt)  # новая функция, если нужно

    await self.repo.save_prompt(user_id, prompt)  # сохранение в БД
