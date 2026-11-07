import { mockApi } from './mock';
import type { Api } from './types';

// Swap in an HTTP implementation here when the backend exists.
export const api: Api = mockApi;
