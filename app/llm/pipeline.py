from langchain import OpenAI
from langchain.schema import HumanMessage
from langchain.chains import LLMChain
from app.llm.vectorstore import get_retriever

class FitAdvisorPipeline:
    def __init__(self, llm_api_key: str | None = None, model_name: str = 'gpt-4'):
        # Подключаем LLM
        self.llm = OpenAI(openai_api_key=llm_api_key, model_name=model_name, temperature=0.2)
        self.retriever = get_retriever()

    async def generate_plan(self, user_profile: dict) -> dict:
        # 1) Выполнить RAG: извлечь релевантные документы по упражнениям/питанию
        docs = self.retriever.get_relevant_documents(user_profile['goals_text'])
        context_text = '\n'.join([d.page_content for d in docs[:6]])

        # 2) Сформировать промпт
        prompt = f"User profile: {user_profile}\n\nContext:\n{context_text}\n\nGenerate: тренировочные рекомендации, диету, план на 4 недели"

        chain = LLMChain(llm=self.llm, prompt=prompt)
        resp = chain.run(prompt)
        # 3) Можно парсить ответ в JSON через второй шаг LLM
        return {'raw': resp}