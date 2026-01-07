import { useAuthStore } from '@/stores/auth';

const API_PREFIX = '/api';
const WRITER_CONFIG_BASE = `${API_PREFIX}/writer-config`;

export interface WriterConfig {
  chapter_versions: number;
}

export interface WriterConfigUpdate {
  chapter_versions: number;
}

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authStore.token}`,
  };
};

export const getWriterConfig = async (): Promise<WriterConfig> => {
  const response = await fetch(WRITER_CONFIG_BASE, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to fetch writer config');
  }
  return response.json();
};

export const updateWriterConfig = async (config: WriterConfigUpdate): Promise<WriterConfig> => {
  const response = await fetch(WRITER_CONFIG_BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    throw new Error('Failed to update writer config');
  }
  return response.json();
};

export const deleteWriterConfig = async (): Promise<void> => {
  const response = await fetch(WRITER_CONFIG_BASE, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to delete writer config');
  }
};
