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
  CircularProgress
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface SemanticMetadata {
  id: number;
  target_table: string;
  business_name: string | null;
  semantic_desc: string | null;
  join_rules: Record<string, any> | null;
  allowed_metrics: string[] | null;
  constraints: string[] | null;
  samples: Record<string, any> | null;
  updated_at: string;
}

interface SemanticMetadataForm {
  target_table: string;
  business_name: string;
  semantic_desc: string;
  join_rules: string; // stringified JSON
  allowed_metrics: string; // comma-separated
  constraints: string; // comma-separated
  samples: string; // stringified JSON
}

const fetchSemanticMetadata = async (): Promise<SemanticMetadata[]> => {
  const response = await fetch('http://localhost:8000/api/semantic_metadata');
  if (!response.ok) {
    throw new Error('Failed to fetch semantic metadata');
  }
  return response.json();
};

const createSemanticMetadata = async (data: SemanticMetadataForm): Promise<SemanticMetadata> => {
  const payload = {
    ...data,
    join_rules: data.join_rules ? JSON.parse(data.join_rules) : null,
    allowed_metrics: data.allowed_metrics ? data.allowed_metrics.split(',').map(s => s.trim()) : null,
    constraints: data.constraints ? data.constraints.split(',').map(s => s.trim()) : null,
    samples: data.samples ? JSON.parse(data.samples) : null,
  };
  const response = await fetch('http://localhost:8000/api/semantic_metadata', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to create semantic metadata');
  }
  return response.json();
};

const updateSemanticMetadata = async (id: number, data: SemanticMetadataForm): Promise<SemanticMetadata> => {
  const payload = {
    ...data,
    join_rules: data.join_rules ? JSON.parse(data.join_rules) : null,
    allowed_metrics: data.allowed_metrics ? data.allowed_metrics.split(',').map(s => s.trim()) : null,
    constraints: data.constraints ? data.constraints.split(',').map(s => s.trim()) : null,
    samples: data.samples ? JSON.parse(data.samples) : null,
  };
  const response = await fetch(`http://localhost:8000/api/semantic_metadata/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to update semantic metadata');
  }
  return response.json();
};

const deleteSemanticMetadata = async (id: number): Promise<void> => {
  const response = await fetch(`http://localhost:8000/api/semantic_metadata/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to delete semantic metadata');
  }
};

const SemanticMetadataTable: React.FC = () => {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery<SemanticMetadata[], Error>({
    queryKey: ['semanticMetadata'],
    queryFn: fetchSemanticMetadata,
  });

  const createMutation = useMutation<SemanticMetadata, Error, SemanticMetadataForm>({
    mutationFn: createSemanticMetadata,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['semanticMetadata'] });
      setOpenDialog(false);
      alert('Semantic Metadata created successfully!');
    },
    onError: (err) => alert(`Error creating Semantic Metadata: ${err.message}`),
  });

  const updateMutation = useMutation<SemanticMetadata, Error, { id: number; data: SemanticMetadataForm }>({
    mutationFn: ({ id, data }) => updateSemanticMetadata(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['semanticMetadata'] });
      setOpenDialog(false);
      alert('Semantic Metadata updated successfully!');
    },
    onError: (err) => alert(`Error updating Semantic Metadata: ${err.message}`),
  });

  const deleteMutation = useMutation<void, Error, number>({
    mutationFn: deleteSemanticMetadata,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['semanticMetadata'] });
      alert('Semantic Metadata deleted successfully!');
    },
    onError: (err) => alert(`Error deleting Semantic Metadata: ${err.message}`),
  });

  const [openDialog, setOpenDialog] = useState(false);
  const [currentMetadata, setCurrentMetadata] = useState<SemanticMetadata | null>(null);
  const [formState, setFormState] = useState<SemanticMetadataForm>({
    target_table: '',
    business_name: '',
    semantic_desc: '',
    join_rules: '',
    allowed_metrics: '',
    constraints: '',
    samples: '',
  });

  const handleOpenDialog = (metadata?: SemanticMetadata) => {
    setCurrentMetadata(metadata || null);
    if (metadata) {
      setFormState({
        target_table: metadata.target_table,
        business_name: metadata.business_name || '',
        semantic_desc: metadata.semantic_desc || '',
        join_rules: metadata.join_rules ? JSON.stringify(metadata.join_rules, null, 2) : '',
        allowed_metrics: metadata.allowed_metrics ? metadata.allowed_metrics.join(', ') : '',
        constraints: metadata.constraints ? metadata.constraints.join(', ') : '',
        samples: metadata.samples ? JSON.stringify(metadata.samples, null, 2) : '',
      });
    } else {
      setFormState({
        target_table: '',
        business_name: '',
        semantic_desc: '',
        join_rules: '',
        allowed_metrics: '',
        constraints: '',
        samples: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setCurrentMetadata(null);
    setFormState({
      target_table: '',
      business_name: '',
      semantic_desc: '',
      join_rules: '',
      allowed_metrics: '',
      constraints: '',
      samples: '',
    });
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    if (currentMetadata) {
      updateMutation.mutate({ id: currentMetadata.id, data: formState });
    } else {
      createMutation.mutate(formState);
    }
  };

  if (isLoading) return (
    <Box display="flex" justifyContent="center" alignItems="center" height="200px">
      <CircularProgress />
      <Typography variant="h6" sx={{ ml: 2 }}>Loading Semantic Metadata...</Typography>
    </Box>
  );
  if (error) return (
    <Typography color="error">Error: {error.message}</Typography>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Semantic Metadata Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Metadata
        </Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Target Table</TableCell>
              <TableCell>Business Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Updated At</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.map((meta) => (
              <TableRow key={meta.id}>
                <TableCell>{meta.id}</TableCell>
                <TableCell>{meta.target_table}</TableCell>
                <TableCell>{meta.business_name || '-'}</TableCell>
                <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {meta.semantic_desc || '-'}
                </TableCell>
                <TableCell>{new Date(meta.updated_at).toLocaleString()}</TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => handleOpenDialog(meta)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={() => deleteMutation.mutate(meta.id)}>
                    <DeleteIcon fontSize="small" color="error" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={openDialog} onClose={handleCloseDialog} fullWidth maxWidth="md">
        <DialogTitle>{currentMetadata ? 'Edit Semantic Metadata' : 'Add Semantic Metadata'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            name="target_table"
            label="Target Table"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.target_table}
            onChange={handleChange}
            sx={{ mb: 2 }}
            disabled={!!currentMetadata} // target_table usually not editable after creation
          />
          <TextField
            margin="dense"
            name="business_name"
            label="Business Name"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.business_name}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="semantic_desc"
            label="Semantic Description"
            type="text"
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            value={formState.semantic_desc}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="join_rules"
            label="Join Rules (JSON)"
            type="text"
            fullWidth
            multiline
            rows={5}
            variant="outlined"
            value={formState.join_rules}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="allowed_metrics"
            label="Allowed Metrics (Comma separated)"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.allowed_metrics}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="constraints"
            label="Constraints (Comma separated)"
            type="text"
            fullWidth
            variant="outlined"
            value={formState.constraints}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="samples"
            label="Samples (JSON)"
            type="text"
            fullWidth
            multiline
            rows={5}
            variant="outlined"
            value={formState.samples}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" color="primary">
            {currentMetadata ? 'Update' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SemanticMetadataTable;
