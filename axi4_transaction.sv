class axi4_txn extends uvm_sequence_item;
`uvm_object_utils(axi4_txn)
  // =========================
  // Basic Attributes
  // =========================
  rand bit is_write;

  rand bit [ID_WIDTH-1:0]   id;
  rand bit [ADDR_WIDTH-1:0] addr;

  // =========================
  // Burst Info
  // =========================
  rand bit [7:0]  len;    // burst length (beats-1)
  rand bit [2:0]  size;   // bytes per beat = 2^size
  rand bit [1:0]  burst;  // FIXED / INCR / WRAP

  // =========================
  // Write Data
  // =========================
  rand bit [DATA_WIDTH-1:0] data[];
  rand bit [DATA_WIDTH/8-1:0] strb[];

  // =========================
  // Response
  // =========================
  bit [1:0] resp[];

  // =========================
  // Utility
  // =========================
  int num_beats;

  constraint c_len {
    len inside {[0:15]}; 
  }
  constraint c_size {
    size inside {[0:3]}; // 1,2,4,8 bytes
  }
  constraint c_array_size {
    data.size() == len + 1;
    strb.size() == len + 1;
  }
  constraint c_write {
    if (is_write) {
      data.size() == len + 1;
    }
  }
  function bit [ADDR_WIDTH-1:0] get_addr(int beat_idx);
    return addr + (beat_idx << size);
  endfunction

  function bit [7:0] get_byte(int beat, int byte_idx);
    return data[beat][8*byte_idx +: 8];
  endfunction

  function string convert2string();
    string s;
    s = $sformatf("AXI4 txn: %s ID=%0d ADDR=0x%0h LEN=%0d",
                   is_write ? "WRITE" : "READ",
                   id, addr, len);
    return s;
  endfunction
endclass
