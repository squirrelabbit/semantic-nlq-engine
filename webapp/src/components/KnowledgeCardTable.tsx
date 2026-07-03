import React, { useState } from 'react';
import {
  Button,
  TextField,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Box,
  Typography,
  CircularProgress,
  Chip
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface KnowledgeCard {
  id: number;
  title: string;
  summary: string;
  tags: string[];
  sources: string[];
  created_at: string;
}

interface KnowledgeCardForm {
  title: string;
  summary: string;
  tags: string; // comma-separated
  sources: string; // comma-separated
}

const fetchKnowledgeCards = async (): Promise<KnowledgeCard[]> => {
  const response = await fetch('http://localhost:8000/api/knowledge_cards');
  if (!response.ok) {
    throw new Error('Failed to fetch knowledge cards');
  }
  return response.json();
};

const createKnowledgeCard = async (data: KnowledgeCardForm): Promise<KnowledgeCard> => {
  const payload = {
    ...data,
    tags: data.tags ? data.tags.split(',').map(s => s.trim()) : [],
    sources: data.sources ? data.sources.split(',').map(s => s.trim()) : [],
  };
  const response = await fetch('http://localhost:8000/api/knowledge_cards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to create knowledge card');
  }
  return response.json();
};

const updateKnowledgeCard = async (id: number, data: KnowledgeCardForm): Promise<KnowledgeCard> => {
  const payload = {
    ...data,
    tags: data.tags ? data.tags.split(',').map(s => s.trim()) : [],
    sources: data.sources ? data.sources.split(',').map(s => s.trim()) : [],
  };
  const response = await fetch(`http://localhost:8000/api/knowledge_cards/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to update knowledge card');
  }
  return response.json();
};

const deleteKnowledgeCard = async (id: number): Promise<void> => {
  const response = await fetch(`http://localhost:8000/api/knowledge_cards/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to delete knowledge card');
  }
};

const KnowledgeCardTable: React.FC = () => {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery<KnowledgeCard[], Error>({
    queryKey: ['knowledgeCards'],
    queryFn: fetchKnowledgeCards,
  });

  const createMutation = useMutation<KnowledgeCard, Error, KnowledgeCardForm>({
    mutationFn: createKnowledgeCard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeCards'] });
      setOpenDialog(false);
      alert('Knowledge Card created successfully!');
    },
    onError: (err) => alert(`Error creating Knowledge Card: ${err.message}`),
  });

  const updateMutation = useMutation<KnowledgeCard, Error, { id: number; data: KnowledgeCardForm }>({
    mutationFn: ({ id, data }) => updateKnowledgeCard(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeCards'] });
      setOpenDialog(false);
      alert('Knowledge Card updated successfully!');
    },
    onError: (err) => alert(`Error updating Knowledge Card: ${err.message}`),
  });

  const deleteMutation = useMutation<void, Error, number>({
    mutationFn: deleteKnowledgeCard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeCards'] });
      alert('Knowledge Card deleted successfully!');
    },
    onError: (err) => alert(`Error deleting Knowledge Card: ${err.message}`),
  });

  const [openDialog, setOpenDialog] = useState(false);
  const [currentCard, setCurrentCard] = useState<KnowledgeCard | null>(null);
  const [formState, setFormState] = useState<KnowledgeCardForm>({
    title: '',
    summary: '',
    tags: '',
    sources: '',
  });

  const handleOpenDialog = (card?: KnowledgeCard) => {
    setCurrentCard(card || null);
    if (card) {
      setFormState({
        title: card.title,
        summary: card.summary,
        tags: card.tags ? card.tags.join(', ') : '',
        sources: card.sources ? card.sources.join(', ') : '',
      });
    } else {
      setFormState({
        title: '',
        summary: '',
        tags: '',
        sources: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setCurrentCard(null);
    setFormState({
      title: '',
      summary: '',
      tags: '',
      sources: '',
    });
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    if (currentCard) {
      updateMutation.mutate({ id: currentCard.id, data: formState });
    } else {
      createMutation.mutate(formState);
    }
  };

  if (isLoading) return (
    <Box display="flex" justifyContent="center" alignItems="center" height="200px">
      <CircularProgress />
      <Typography variant="h6" sx={{ ml: 2 }}>Loading Knowledge Cards...</Typography>
    </Box>
  );
  if (error) return (
    <Typography color="error">Error: {error.message}</Typography>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Knowledge Card Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Knowledge Card
        </Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Title</TableCell>
              <TableCell>Summary</TableCell>
              <TableCell>Tags</TableCell>
              <TableCell>Created At</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.map((card) => (
              <TableRow key={card.id}>
                <TableCell>{card.id}</TableCell>
                <TableCell>{card.title}</TableCell>
                <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {card.summary}
                </TableCell>
                <TableCell>
                  {card.tags?.map((tag, index) => (
                    <Chip key={index} label={tag} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>{new Date(card.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => handleOpenDialog(card)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={() => deleteMutation.mutate(card.id)}>
                    <DeleteIcon fontSize="small" color="error" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={openDialog} onClose={handleCloseDialog} fullWidth maxWidth="md">
        <DialogTitle>{currentCard ? 'Edit Knowledge Card' : 'Add Knowledge Card'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            name="title"
            label="Title"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.title}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="summary"
            label="Summary"
            type="text"
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            value={formState.summary}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="tags"
            label="Tags (Comma separated)"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.tags}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="sources"
            label="Sources (Comma separated)"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.sources}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" color="primary">
            {currentCard ? 'Update' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KnowledgeCardTable;