import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface ChatMessage {
  message: string
  memory_enabled?: boolean
  thread_id?: string | null
}

export interface ToolCall {
  name: string
  arguments: Record<string, any>
  output: any
}

export interface ReasoningStep {
  step_number: number
  reasoning?: string
  tool_calls: ToolCall[]
}

export interface AgentContext {
  system_prompt: string
  memory_enabled: boolean
  preferences_applied?: string | null
  model: string
  available_tools: string[]
}

export interface ChatResponse {
  response: string
  reasoning_steps: ReasoningStep[]
  agent_context?: AgentContext | null
  thread_id?: string | null
}

export interface ThreadInfo {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
  last_message_at?: string | null
  message_count: number
}

export interface ThreadMessage {
  id: string
  text: string
  sender: 'user' | 'agent'
  timestamp?: string | null
  reasoning_steps?: ReasoningStep[] | null
  agent_context?: AgentContext | null
}

export interface ThreadDetail {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
  last_message_at?: string | null
  messages: ThreadMessage[]
  message_count: number
}

export interface Category {
  categories: string[]
}

export interface PreferenceStatus {
  total_preferences: number
  categories: string[]
}

export interface Preference {
  id: string
  category: string
  preference: string
  context: string
  confidence: number
  created_at: string
  last_updated: string
}

export interface GraphNode {
  id: string
  labels: string[]
  properties: Record<string, any>
}

export interface GraphRelationship {
  id: string
  from: string
  to: string
  type: string
  properties: Record<string, any>
}

export interface MemoryGraph {
  nodes: GraphNode[]
  relationships: GraphRelationship[]
}

export const chatAPI = {
  sendMessage: async (
    message: string, 
    memoryEnabled: boolean = false,
    threadId: string | null = null
  ): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat', { 
      message,
      memory_enabled: memoryEnabled,
      thread_id: threadId
    })
    return response.data
  },

  getCategories: async (): Promise<string[]> => {
    const response = await api.get<Category>('/categories')
    return response.data.categories
  },

  healthCheck: async (): Promise<boolean> => {
    try {
      const response = await api.get('/health')
      return response.status === 200
    } catch {
      return false
    }
  },

  getPreferencesStatus: async (): Promise<PreferenceStatus> => {
    const response = await api.get<PreferenceStatus>('/preferences/status')
    return response.data
  },

  getPreferences: async (): Promise<Preference[]> => {
    const response = await api.get<Preference[]>('/preferences/list')
    return response.data
  },

  clearPreferences: async (): Promise<string> => {
    const response = await api.post('/preferences/clear')
    return response.data.message
  },

  deletePreference: async (preferenceId: string): Promise<string> => {
    const response = await api.delete(`/preferences/${preferenceId}`)
    return response.data.message
  },

  getMemoryGraph: async (): Promise<MemoryGraph> => {
    const response = await api.get<MemoryGraph>('/preferences/graph')
    return response.data
  },

  // Thread management
  getThreads: async (): Promise<ThreadInfo[]> => {
    const response = await api.get<ThreadInfo[]>('/threads')
    return response.data
  },

  getThread: async (threadId: string): Promise<ThreadDetail> => {
    const response = await api.get<ThreadDetail>(`/threads/${threadId}`)
    return response.data
  },

  createThread: async (title?: string): Promise<ThreadInfo> => {
    const response = await api.post<ThreadInfo>('/threads', { title })
    return response.data
  },

  updateThreadTitle: async (threadId: string, title: string): Promise<string> => {
    const response = await api.put(`/threads/${threadId}/title`, { title })
    return response.data.message
  },

  deleteThread: async (threadId: string): Promise<string> => {
    const response = await api.delete(`/threads/${threadId}`)
    return response.data.message
  },

  getLastActiveThread: async (): Promise<ThreadInfo | null> => {
    const response = await api.get<ThreadInfo | null>('/threads/last-active')
    return response.data
  },
}

export default api
