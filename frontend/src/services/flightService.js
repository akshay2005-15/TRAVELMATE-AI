import api from './api';

export const flightService = {
  // Search flight offers matching criteria
  searchFlights: async (criteria) => {
    const response = await api.post('/flights/search', criteria);
    return response.data;
  },

  // Query airport autocomplete directory
  getAirports: async (query = '') => {
    const response = await api.get('/flights/airports', {
      params: { q: query },
    });
    return response.data;
  },

  // Get active provider status
  getProviderStatus: async () => {
    const response = await api.get('/flights/provider-status');
    return response.data;
  },

  // Retrieve stored search by ID
  getSavedSearch: async (searchId) => {
    const response = await api.get(`/flights/searches/${searchId}`);
    return response.data;
  },
};

