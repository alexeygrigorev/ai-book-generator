#!/usr/bin/env python
# coding: utf-8

# In[ ]:





# In[1]:


from google import genai
from google.genai import types


# In[61]:


def calculate_gemini_3_cost(usage_metadata, print_cost=False):
    """
    Calculates cost for Gemini 3 Pro Preview based on usage_metadata object.
    Automatically handles the pricing tiers for prompts above/below 200k tokens.
    """

    # 1. Safely extract token counts (handling both object attributes and dict keys)
    def get_val(data, attr):
        return getattr(data, attr, data.get(attr, 0)) if hasattr(data, 'get') else getattr(data, attr, 0)

    prompt_tokens = get_val(usage_metadata, 'prompt_token_count')
    candidates_tokens = get_val(usage_metadata, 'candidates_token_count')
    # Use 0 if thoughts_token_count is missing (backward compatibility)
    thoughts_tokens = get_val(usage_metadata, 'thoughts_token_count') 

    # 2. Determine Pricing Tier (Nov 2025 Rates)
    # If prompt is > 200k, rates increase for both input and output
    if prompt_tokens > 200_000:
        input_rate = 4.00
        output_rate = 18.00
        tier_name = "Long Context (>200k)"
    else:
        input_rate = 2.00
        output_rate = 12.00
        tier_name = "Standard (<200k)"

    # 3. Calculate Costs
    # Thoughts are billed as output tokens
    total_output_tokens = candidates_tokens + thoughts_tokens

    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (total_output_tokens / 1_000_000) * output_rate
    total_cost = input_cost + output_cost

    if print_cost:
        # 4. Print Report
        print(f"--- Gemini 3 Pro Cost Report ---")
        print(f"Tier:            {tier_name}")
        print(f"Prompt Tokens:   {prompt_tokens:,}  (@ ${input_rate}/1M)")
        print(f"Output Tokens:   {total_output_tokens:,}  (@ ${output_rate}/1M)")
        print(f"  - Candidates:  {candidates_tokens:,}")
        print(f"  - Thoughts:    {thoughts_tokens:,}")
        print(f"--------------------------------")
        print(f"Input Cost:      ${input_cost:.6f}")
        print(f"Output Cost:     ${output_cost:.6f}")
        print(f"TOTAL COST:      ${total_cost:.6f}")

    return total_cost


# In[3]:


gemini_client = genai.Client()


# In[4]:


from pydantic import BaseModel


# In[5]:


planner_instructions = """
Your role is planning the book. 

You're given a conversation beween a user and an assistant about a book. Based 
on the conversation, you need to create a detailed book plan with each chapter
and section. Later we will give this to the writer, who will actually write the book.

A chapter should have at least 4 sections, and each section should have at least 7-8 bullet
points. 

Often the input doesn't contain all the information you need, so you must use your knowledge
to make sure the output is comprehensive.

The language of the output should match the language of the input.

Do not add numbers to chapter and section names. It will be added later automatically.
"""


# In[6]:


class BookSectionPlan(BaseModel):
    name: str
    bullet_points: list[str]

class BookChapterPlan(BaseModel):
    name: str
    # chapter_intro: str
    sections: list[BookSectionPlan]

class BookPartPlan(BaseModel):
    name: str
    introduction: str
    chapters: list[BookChapterPlan]

class BookPlan(BaseModel):
    name: str
    target_reader: str
    back_cover_description: str
    parts: list[BookPartPlan]


# In[32]:


book_plan_input = """
Общепопулярная книга про сирены для читателей всех возрастов. Никаких особенных предварительных 
знаний от читателя не требуется.

В книге должно быть 15-20 глав

Вот вариант оглавления для книги о сиренах (системах звукового оповещения) – именно про воздушные тревоги, промышленные и т.п.
Введение

Что такое сирена
1.1. Определение и отличие от просто «громкой сигнализации» 
1.2. История: от механических воздушных тревог до электронных систем массового оповещения 
1.3. Роль сирен в современных системах гражданской обороны и промышленной безопасности

Где и зачем используются сирены
2.1. Гражданская оборона и воздушная тревога
2.2. Природные ЧС: цунами, наводнения, торнадо и пр. 
2.3. Промышленные объекты и опасные производства
2.4. Транспорт: пожарные, полиция, скорая, спецтехника
2.5. Локальные охранные и технологические сирены

Часть I. Физика и восприятие сиренного сигнала

Основы акустики для конструкторов и операторов
3.1. Частота, уровень звукового давления, спектр
3.2. Распространение звука в городской и сельской среде
3.3. Затухание, отражения, «теневые зоны»

Человек и сиренный звук
4.1. Слух и восприятие тревожных сигналов
4.2. Различимость тонов и кодированных сигналов
4.3. Ограничения по уровню шума и здоровье персонала

Часть II. Классификация сирен

По принципу действия
5.1. Механические сирены

Ротор-статор, воздушный поток, привод 
Однотональные, двухтональные, многотональные
5.2. Электромеханические сирены
Электродвигатель + механический звукоизлучатель
Типичные мощности и области применения 

5.3. Электронные сирены

Генерация тона, усилители, рупорные громкоговорители 

Возможность голосового оповещения и речевых сообщений 

5.4. Пневматические и воздушные сирены (компрессорные системы)
5.5. Ручные (hand-crank) сирены и портативные решения 

По направленности излучения
6.1. Всенаправленные (омнидирекционные) сирены
6.2. Направленные и ротационные сирены (вращающиеся головки) 
6.3. Многонаправленные электронные массивы (cluster horn arrays)

По назначению
7.1. Сирены гражданской обороны и воздушной тревоги
7.2. Промышленные и объектовые сирены
7.3. Сирены систем раннего оповещения о стихийных бедствиях
7.4. Сирены на транспортных средствах
7.5. Охранные, технологические и бытовые сирены

Часть III. Конструкция и элементы сирен

Механическая часть
8.1. Роторы и статоры: геометрия и число портов
8.2. Рупоры и акустические излучатели
8.3. Материалы корпусов и защита от окружающей среды

Электроника и управление
9.1. Блоки питания: AC, DC, комбинированные, аккумуляторные 
9.2. Усилители мощности и драйверы громкоговорителей
9.3. Контроллеры: локальные панели, PLC, встроенные микроконтроллеры
9.4. Радио-управление, проводное управление, IP-управление

Интеграция в системы оповещения
10.1. Городские и региональные системы массового оповещения
10.2. Системы оповещения на промышленных предприятиях
10.3. Интеграция с радиовещанием, ТВ, мобильными оповещениями (Cell Broadcast, EU-Alert и аналогичные системы) 


Часть IV. Виды сигналов и их кодирование

Типовые сигналы тревоги
11.1. Непрерывный тон
11.2. Модулированный (вой) тон
11.3. Импульсные и прерывистые сигналы
11.4. Комбинированные схемы (high-low, “yelp”, “wail” и др.) 


Стандартизация сигналов по странам
12.1. Примеры национальных систем (Европа, США, Азия и др.) 
12.2. Проблема унификации: туристы, мигранты, международные объекты
12.3. Использование голосовых сообщений вместе с сиренами

Проектирование “звукового кода” для объекта
13.1. Различение видов опасностей по тону
13.2. Минимальное количество сигналов для эффективной системы
13.3. Учет людей с нарушениями слуха и зрения

Часть V. Производители и модельные ряды

Крупные мировые производители сирен
14.1. Federal Signal (США): механические и электронные “giant voice” сирены 
14.2. Whelen Engineering (США): электронные вращающиеся и статичные массивы 
14.3. American Signal Corporation (ASC, США): механические и электронные системы оповещения 
14.4. Hörmann Warnsysteme (Германия): городские и промышленно-объектовые системы 
14.5. Telegrafia (Словакия) и другие европейские производители 
14.6. Другие бренды и региональные производители

Сравнение подходов крупных производителей
15.1. Конструкция и типовые мощности
15.2. Философия системного решения: “просто сирена” vs “платформа массового оповещения”
15.3. Поддержка стандартов, протоколов и интеграций

Обзор типовых моделей сирен
16.1. Городские всенаправленные сирены
16.2. Направленные/ротационные “дальнобойные” установки
16.3. Промышленные и цеховые сирены
16.4. Компактные и специализированные модели (в т.ч. вроде 500DHE-TT и аналогичных)
16.5. Сравнительные таблицы:

Звуковое давление (дБ на 30/60/100 м)
Диапазон частот
Потребляемая мощность
Тип питания и резервирование
Интерфейсы управления

Часть VI. Проектирование и выбор сирен под задачу

Методика выбора сирен
17.1. Анализ рисков и сценариев опасности
17.2. Требуемый уровень звука и зона покрытия
17.3. Выбор типа (механическая/электронная, направленная/омни)
17.4. Резервирование и отказоустойчивость

Расчёт размещения сирен
18.1. Модели распространения звука в городах и на промплощадках
18.2. Использование ГИС и акустического моделирования
18.3. Оптимизация количества и мощности сирен

Примеры типовых проектов
19.1. Небольшой промышленный объект
19.2. Город районного масштаба
19.3. Крупный промышленный кластер с несколькими опасными производствами

Часть VII. Эксплуатация, обслуживание и модернизация

Эксплуатация и регламентные работы
20.1. Периодические проверки и тестовые включения (полные и «growl»-тесты) 
20.2. Документирование срабатываний и проверок
20.3. Организация службы эксплуатации

Надёжность и типовые откази
21.1. Характерные неисправности механических сирен
21.2. Характерные неисправности электронных сирен
21.3. Диагностика, удалённый мониторинг и телеметрия

Модернизация существующих систем
22.1. Замена устаревших механических сирен на электронные
22.2. Добавление голосового оповещения
22.3. Переход к цифровому/IP-управлению и интеграция в комплексные системы безопасности

Часть VIII. Нормативные требования и будущее сирен

Нормативы и стандарты
23.1. Международные и европейские стандарты
23.2. Национальные требования (на примерах нескольких стран)
23.3. Требования к уровню шума, надёжности, резервированию

Тренды и инновации
24.1. Интеграция сирен с мобильными оповещениями и “умными городами” 
24.2. Использование цифровой обработки сигнала и направленных массивов
24.3. Перспективы: останутся ли сирены в эпоху смартфонов?

Приложения

A. Каталог модельных рядов (пример)

Таблицы с техническими характеристиками для ряда моделей (в т.ч. условные 500DHE-TT и подобные: паспортные данные, назначение, рекомендуемое применение).

B. Примеры звуковых сигналов

Описание формы сигнала и применение.

C. Шаблоны документов

Журнал испытаний сирен

Форма паспорта сирены

Пример регламента эксплуатации
"""


# In[ ]:





# In[33]:


plan_response = gemini_client.models.generate_content(
    model="models/gemini-3-pro-preview",
    config=types.GenerateContentConfig(
        system_instruction=planner_instructions,
        response_mime_type="application/json",
        response_json_schema=BookPlan.model_json_schema(),
    ),
    contents=book_plan_input
)


# In[62]:


calculate_gemini_3_cost(plan_response.usage_metadata, print_cost=True)


# In[35]:


book_plan = BookPlan.model_validate(plan_response.parsed)


# In[36]:


from pathlib import Path


# In[37]:


root_folder = Path('sirens')
root_folder.mkdir(exist_ok=True)


# In[ ]:





# In[38]:


import yaml


# In[39]:


plan_yaml = root_folder / 'plan.yaml'

with plan_yaml.open('wt', encoding='utf-8') as f_out:
    yaml.safe_dump(
        book_plan.model_dump(),
        f_out,
        allow_unicode=True,
        sort_keys=False
    )


# In[41]:


print('===', book_plan.name, '===')
print()
print(book_plan.target_reader)
print()
print(book_plan.back_cover_description)
print()
print()

for part in book_plan.parts:
    print('---', part.name, '---')
    print() 
    print(part.introduction)
    print()

    for chapter in part.chapters:
        print('#', chapter.name)
        print()

        for section in chapter.sections:
            print('##', section.name)
            print()
            for bp in section.bullet_points:
                print('-', bp)

            print()    


# In[42]:


book_plan.target_reader


# In[58]:


writer_instructions = """
Your task is based on the plan write a book section. 
You execute it section-by-section and you're given the current progress

A section should contain 800-1200 words. Don't use lists, use proper sentences,
The style is a a popular science book.

Output markdown, and use only level-3 headings. 

The output language should match the input language.
""".strip()

chapter_intro_instructions = """
Based on the chapter outline, you should write an introduction to the chapter 
describing what the chapter will cover. 

It should be 50-80 words. Don't include lists, it should be proper sentences.

The output language should match the input language.
"""


# In[44]:


from dataclasses import dataclass


# In[45]:


@dataclass
class ChapterSpecs:
    part: BookPartPlan
    part_number: int

    chapter: BookChapterPlan
    chapter_number: int

    sections: list[BookSectionPlan]


# In[46]:


part_idx = 0
chapter_idx = 0

chapter_specs = []

for part in book_plan.parts:
    part_idx = part_idx + 1

    for chapter in part.chapters:
        chapter_idx = chapter_idx + 1

        specs = ChapterSpecs(
            part=part,
            part_number=part_idx,
            chapter=chapter,
            chapter_number=chapter_idx,
            sections=chapter.sections
        )

        chapter_specs.append(specs)


# In[47]:


len(chapter_specs)


# In[48]:


from tqdm.auto import tqdm


# In[50]:


def llm(instructions, prompt, model="models/gemini-3-pro-preview"):
    response = gemini_client.models.generate_content(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=instructions,
        ),
        contents=prompt
    )
    return response


# In[78]:


specs = chapter_specs[0]


# In[108]:


chapters_done = []
chapters_todo = chapter_specs[::-1]


# In[109]:


chapters_current = chapters_todo.pop()


# In[110]:


chapter_overview = yaml.safe_dump(
    chapters_current.chapter.model_dump(),
    allow_unicode=True,
    sort_keys=False
)

intro_response = llm(chapter_intro_instructions, chapter_overview)

intro_cost = calculate_gemini_3_cost(intro_response.usage_metadata)
print(f'{intro_cost=}')

part_folder = root_folder / f'part_{specs.part_number:02d}'
part_folder.mkdir(exist_ok=True)
intro_file = part_folder / f'{specs.chapter_number:02d}_00_intro.md'


intro_text = intro_response.text
intro_full_text = f"""
# {specs.chapter_number}. {specs.chapter.name}

{intro_text}
""".strip()

intro_file.write_text(intro_full_text, encoding='utf-8')


# In[129]:


def show_progress(done, current, todo, name_function):
    progress_builder = []

    for c in done:
        line = f'[x] {name_function(c)}'
        progress_builder.append(line)

    line = f"[ ] {name_function(current)} <-- YOU'RE CURRENTLY HERE"
    progress_builder.append(line)

    for c in reversed(todo):
        line = f'[ ] {name_function(c)}'
        progress_builder.append(line)

    progress = '\n'.join(progress_builder)

    return progress


# In[122]:


section_prompt_template = """
The chapter name: {chapter_name}

The section name: {section_name}

Outline: 

{section_outline}

Current chapter progress:

{chapter_progress}

Current book progress:

{book_progress}
""".strip()


# In[130]:


book_progress = show_progress(
    chapters_done,
    chapters_current,
    chapters_todo,
    name_function=lambda c: c.chapter.name
)


# In[171]:


sections_completed = []
sections_todo = chapters_current.sections[::-1]


# In[172]:


while len(sections_todo) > 0:
    current_section = sections_todo.pop()
    print(current_section)

    chapter_progress = show_progress(
        sections_completed,
        current_section,
        sections_todo,
        name_function=lambda c: c.name
    )

    section_outline = '\n'.join(current_section.bullet_points)

    section_prompt = section_prompt_template.format(
        chapter_name=current.chapter.name,
        section_name=section.name,
        section_outline=section_outline,
        chapter_progress=chapter_progress,
        book_progress=book_progress
    )

    print(section_prompt)

    section_response = llm(instructions=writer_instructions, prompt=section_prompt)
    section_cost = calculate_gemini_3_cost(section_response.usage_metadata)
    print(f'{section_cost=}')

    section_number = len(sections_completed) + 1

    section_file = part_folder / f'{specs.chapter_number:02d}_{section_number:02d}_section.md'
    full_section_text = f"""
## {current_section.name}

{section_response.text}
""".strip()

    section_file.write_text(full_section_text, encoding='utf-8')
    sections_completed.append(current_section)

    print()


# In[ ]:




