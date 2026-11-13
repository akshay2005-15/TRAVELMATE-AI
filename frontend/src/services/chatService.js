import api from './api';

export const chatService = {
  /**
   * Send a message to the AI flight booking assistant.
   * @param {string} message - User travel query
   * @param {number|null} conversationId - Optional conversation ID for continuation
   * @returns {Promise<ChatMessageResponse>}
   */
  sendMessage: async (message, conversationId = null) => {
    const payload = {
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    };
    const response = await api.post('/chat/message', payload);
    return response.data;
  },

  /**
   * Retrieve all conversations belonging to the current user.
   * @returns {Promise<Array<ConversationSummaryResponse>>}
   */
  getConversations: async () => {
    const response = await api.get('/chat/conversations');
    return response.data;
  },

  /**
   * Retrieve full conversation message history in chronological order.
   * @param {number} conversationId
   * @returns {Promise<ConversationResponse>}
   */
  getConversationHistory: async (conversationId) => {
    const response = await api.get(`/chat/conversations/${conversationId}`);
    return response.data;
  },

  /**
   * Delete a conversation session and all its messages.
   * @param {number} conversationId
   * @returns {Promise<{ status: string, message: string }>}
   */
  deleteConversation: async (conversationId) => {
    const response = await api.delete(`/chat/conversations/${conversationId}`);
    return response.data;
  },
};

export default chatService;

