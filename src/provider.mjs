const defaultOllamaBaseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";

export function createAnalysisModel() {
  const provider = (process.env.AI_PROVIDER || "ollama").toLowerCase();

  if (provider === "openai-compatible") {
    return {
      provider,
      modelName: process.env.OPENAI_MODEL || "local-model",
      healthcheck: async () => {
        const ok = Boolean(process.env.OPENAI_BASE_URL);
        return ok ? "OpenAI-compatible endpoint configured." : "Missing OPENAI_BASE_URL.";
      },
      generate: generateViaOpenAICompatible
    };
  }

  const configuredModel = process.env.OLLAMA_MODEL || "llama3.2:latest";

  return {
    provider: "ollama",
    modelName: configuredModel,
    healthcheck: async () => {
      try {
        const response = await fetch(`${defaultOllamaBaseUrl}/api/tags`);
        if (!response.ok) {
          return `Ollama responded with ${response.status} ${response.statusText}`;
        }
        const data = await response.json();
        const models = Array.isArray(data.models) ? data.models.map((m) => m.name) : [];
        if (models.length === 0) {
          return "Ollama is reachable, but no models are installed. Run `ollama pull llama3.2` to install one.";
        }
        const exactOrPrefixMatch = models.some((m) => m === configuredModel || m.startsWith(configuredModel.split(":")[0]));
        if (exactOrPrefixMatch) {
          return `Ollama is reachable. Model "${configuredModel}" is ready.`;
        }
        return `Ollama is reachable. Note: configured model "${configuredModel}" not found. Installed: ${models.join(", ")}`;
      } catch (error) {
        return `Ollama is not reachable at ${defaultOllamaBaseUrl}: ${error.message}`;
      }
    },
    generate: async (options) => {
      const targetModel = options.model || configuredModel;
      return generateViaOllama({ ...options, model: targetModel });
    }
  };
}

async function generateViaOllama({ messages, model }) {
  const response = await fetch(`${defaultOllamaBaseUrl}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      messages,
      stream: false
    })
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();
  return payload?.message?.content ?? "";
}

async function generateViaOpenAICompatible({ messages, model }) {
  const baseUrl = process.env.OPENAI_BASE_URL;
  const apiKey = process.env.OPENAI_API_KEY || "";

  if (!baseUrl) {
    throw new Error("OPENAI_BASE_URL is required for AI_PROVIDER=openai-compatible");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {})
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.2
    })
  });

  if (!response.ok) {
    throw new Error(`OpenAI-compatible request failed: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();
  return payload?.choices?.[0]?.message?.content ?? "";
}

