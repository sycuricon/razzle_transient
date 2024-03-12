from Instruction import *
from MagicDevice import *
from Block import *

class TransBlock:
    def __init__(self, name, extension, default):
        self.name = name
        self.inst_list = []
        self.data_list = []
        self.extension = extension
        self.default = default

    def _load_raw_asm(self,file_name):
        file_name=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..',file_name)
        with open(file_name,"rt") as file:
            file_list = file.readlines()
        inst_list = [RawInstruction(line.strip()) for line in file_list]
        return inst_list

    def is_default(self):
        return self.default
    
    def need_store(self):
        if self.default:
            return {'t0', 't1'}
        else:
            rd_list = set()
            for inst in self.inst_list:
                if inst.has('RD'):
                    rd_list.add(inst['RD'])
            return rd_list
    
    def gen_instr(self):
        if self.default:
            self.gen_default()
        else:
            self.gen_random()
    
    def gen_random(self):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self):
        raise "Error: gen_default not implemented!"

    def gen_asm(self):
        inst_asm_list = []
        inst_asm_list.append(f'{self.name}:\n')
        for item in self.inst_list:
            inst_asm_list.append(item.to_asm()+'\n')
        data_asm_list = []
        data_asm_list.append(f'{self.name}_data:\n')
        for item in self.data_list:
            data_asm_list.append(item.to_asm()+'\n')
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0

class TrapBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)
    
    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/trap.text.S")
        self.data_list=self._load_raw_asm("env/trans/trap.data.S")

class FunctionEndBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/func_end.text.S")
        self.data_list=self._load_raw_asm("env/trans/func_end.data.S")

class ExitBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/exit.text.S")
        self.data_list=self._load_raw_asm("env/trans/exit.data.S")

class PocFuncBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/poc_func.text.S")
    
class DelayBlock(TransBlock):
    def __init__(self, name, extension, default):
        super().__init__(name, extension, default)

    def _gen_dep_list(self):
        self.GPR_list = [reg for reg in reg_range if reg not in ['A0','A1','ZERO']]
        self.FLOAT_list = float_range
        dep_list = []
        for i in range(random.randint(6,8)):
            if random.random() < 0.8:
                dep_list.append(random.choice(self.GPR_list))
            else:
                dep_list.append(random.choice(self.FLOAT_list))
        dep_list.append(random.choice(self.GPR_list))
        return dep_list
    
    def _gen_inst_list(self, dep_list):
        for i, src in enumerate(dep_list[0:-1]):
            dest = dep_list[i+1]
            if src in self.GPR_list and dest in self.FLOAT_list:
                self.inst_list.append(Instruction(f'fcvt.s.lu   {dest.lower()}, {src.lower()}'))
            elif src in self.FLOAT_list and dest in self.GPR_list:
                self.inst_list.append(Instruction(f'fcvt.lu.s   {dest.lower()}, {src.lower()}'))
            elif src in self.FLOAT_list and dest in self.FLOAT_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint([extension for extension in [\
                        'RV_D', 'RV64_D',\
                        'RV_F', 'RV64_F',\
                        'RV32_C_F', 'RV_C_D'\
                    ] if extension in self.extension])
                    instr.set_category_constraint(['FLOAT'])

                    def c_dest(name, frd):
                        return use_frd(name) and use_frs1(name) and frd == dest
                    instr.add_constraint(c_dest, ['NAME','FRD'])
                    instr.solve()

                    freg_list = [freg for freg in ['FRS1','FRS2','FRS3'] if instr.has(freg)]
                    for freg in freg_list:
                        if freg == src:
                            break
                    else:
                        instr[random.choice(freg_list)] = src

                    if instr.has('FRD'):
                        self.inst_list.append(instr)
                        break

            elif src in self.GPR_list and dest in self.GPR_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint(self.extension)
                    instr.set_category_constraint(['ARITHMETIC'])

                    def c_dest(rd):
                        return rd == dest
                    def c_src(name, rs1, rs2):
                        return use_rs1(name) and (rs1 == src or use_rs2(name) and rs2 == src)
                    def c_reg_range(name, rs1, rs2):
                        return rs1 in self.GPR_list and (not use_rs2(name) or rs2 in self.GPR_list)
                    instr.add_constraint(c_dest,['RD'])
                    instr.add_constraint(c_src,['NAME','RS1','RS2'])
                    instr.add_constraint(c_reg_range, ['NAME','RS1','RS2'])
                    instr.solve()

                    if instr.has('RD'):
                        self.inst_list.append(instr)
                        break
    
    def _gen_init_inst(self, dep_list):
        float_init_list = set()
        float_inited_list = set()
        GPR_init_list = set()
        GPR_inited_list = set()
        for dest_reg,inst in zip(dep_list, self.inst_list):

            if inst.has('FRS1'):
                if inst['FRS1'] not in float_inited_list:
                    float_init_list.add(inst['FRS1'])
            if inst.has('FRS2'):
                if inst['FRS2'] not in float_inited_list:
                    float_init_list.add(inst['FRS2'])
            if inst.has('FRS3'):
                if inst['FRS3'] not in float_inited_list:
                    float_init_list.add(inst['FRS3'])
            if inst.has('RS1'):
                if inst['RS1'] not in GPR_inited_list:
                    GPR_init_list.add(inst['RS1'])
            if inst.has('RS2'):
                if inst['RS2'] not in GPR_inited_list:
                    GPR_init_list.add(inst['RS2'])

            if dest_reg[0] == 'F':
                float_inited_list.add(dest_reg)
            else:
                GPR_inited_list.add(dest_reg)
        
        tmp_inst_list = []
        for freg in float_init_list:
            tmp_inst_list.append(RawInstruction(f'li t0, {random.randint(0, 2**64)}'))
            tmp_inst_list.append(RawInstruction(f'fcvt.s.lu   {freg.lower()}, t0'))
        for reg in GPR_init_list:
            tmp_inst_list.append(RawInstruction(f'li {reg.lower()}, {random.randint(0, 2**64)}'))
        for i in range(16):
            tmp_inst_list.append(RawInstruction('nop'))
        self.inst_list = tmp_inst_list + self.inst_list

    def gen_random(self):
        dep_list = self._gen_dep_list()
        self._gen_inst_list(dep_list)
        self._gen_init_inst(dep_list)
        self.result_imm = 0
        self.result_reg = dep_list[-1]

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/delay.text.S")
        self.data_list=self._load_raw_asm("env/trans/delay.data.S")
        self.result_reg = 't0'.upper()
        self.result_imm = 0
    
    def get_result_reg(self):
        return self.result_reg

class PocBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/poc.text.S")
    
class VictimBlock(TransBlock):
    def __init__(self, name, extension, default, predict_block):
        super().__init__(name, extension, default)
        self.predict_block=predict_block

    def gen_random(self):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/victim.text.S")
        self.inst_list.append(RawInstruction(f'j {self.predict_block}'))

class InitSecretBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/init_secret.text.S")
        self.data_list=self._load_raw_asm("env/trans/init_secret.data.S")

class PredictBlock(TransBlock):
    def __init__(self, name, extension, default, result_reg, result_imm, predict_kind, correct_block):
        super().__init__(name, extension, default)
        self.result_reg = result_reg
        self.result_imm = result_imm
        self.predict_kind = predict_kind
        self.correct_block = correct_block
        self.imm = 0

    def gen_random(self):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self):
        self.inst_list.append(RawInstruction(f'xor {self.result_reg.lower()}, {self.result_reg.lower()}, {self.result_reg.lower()}'))
        match(self.predict_kind):
            case 'call':
                delay_link_inst = Instruction(f'add t0, {self.result_reg.lower()}, a0')
                self.inst_list.append(delay_link_inst)
                call_inst = Instruction()
                call_inst.set_name_constraint(['JALR'])
                call_inst.set_category_constraint(['JUMP'])
                call_inst.set_extension_constraint(['RV_I'])
                def c_call(rd, rs1):
                    return rd == 'RA' and rs1 == 'T0'
                call_inst.add_constraint(c_call,['RD','RS1'],True)
                call_inst.solve()

                self.imm = call_inst['IMM']
                self.inst_list.append(call_inst)
            case 'return':
                delay_link_inst = Instruction(f'add ra, {self.result_reg}, a0')
                self.inst_list.append(delay_link_inst)
                ret_inst = Instruction()
                ret_inst.set_name_constraint(['JALR'])
                ret_inst.set_category_constraint(['JUMP'])
                ret_inst.set_extension_constraint(['RV_I'])
                ret_inst.set_imm_constraint(range(0,1))
                def c_ret(rd, rs1):
                    return rd == 'ZERO' and rs1 == 'RA'
                ret_inst.add_constraint(c_ret,['RD','RS1'],True)
                ret_inst.solve()

                self.imm = ret_inst['IMM']
                self.inst_list.append(ret_inst)
            case 'branch_taken'|'branch_not_taken':
                ret_inst = Instruction()
                ret_inst.set_category_constraint(['BRANCH'])
                ret_inst.set_extension_constraint(['RV_I'])
                if self.predict_kind=='branch_taken':
                    ret_inst.set_label_constraint(['func_end'])
                else:
                    ret_inst.set_label_constraint(['victim'])
                def c_param(NAME,RS1,RS2):
                    return ((NAME in ['BLT','BGE'] and self.imm != -2 ** (64 - 1) and self.imm != 2 ** (64 - 1) - 1) \
                        or (NAME in ['BLTU','BGEU'] and self.imm != 0 and self.imm != 2 ** 64 - 1)\
                        or (NAME in ['BEQ','BNE'])) and RS1=='A0' and RS2==self.result_reg
                ret_inst.add_constraint(c_param,['NAME','RS1','RS2'])
                ret_inst.solve()
            
                self.branch_kind=ret_inst['NAME']
                self.inst_list.append(ret_inst)
            case _:
                raise "Error: predict_kind not implemented!"

class TrainBlock(TransBlock):
    def __init__(self, name, extension, default, train_loop, victim_loop,\
                predict_kind, correct_block, false_block, imm_param):
        super().__init__(name, extension, default)
        self.predict_kind = predict_kind
        self.correct_block = correct_block
        self.false_block = false_block
        self.imm_param = imm_param
        self.train_loop = train_loop
        self.victim_loop = victim_loop
    
    def _gen_predict_param(self):
        match(self.predict_kind):
            case 'call' | 'return':
                false_predict_param = f"{self.false_block} - {self.imm_param['predict']}"
                true_predict_param = f"{self.correct_block} - {self.imm_param['delay']} - {self.imm_param['predict']}"
            case 'branch_taken'|'branch_not_taken':
                match(self.imm_param['branch_kind']):
                    case 'BEQ':
                        false_predict_param = self.imm_param['predict'] + 1 if self.imm_param['predict'] == 0 else self.imm_param['predict'] - 1
                        true_predict_param = self.imm_param['predict']
                    case 'BNE':
                        false_predict_param = self.imm_param['predict']
                        true_predict_param = self.imm_param['predict'] + 1 if self.imm_param['predict'] == 0 else self.imm_param['predict'] - 1
                    case 'BLT':
                        assert(self.imm_param['predict']!=-2 ** (64 - 1) and self.imm_param['predict']!=2 ** (64 - 1) - 1)
                        false_predict_param = random.randint(self.imm_param['predict'], 2 ** (64 - 1))
                        true_predict_param = random.randint(-2 ** (64 - 1), self.imm_param['predict'])
                    case 'BGE':
                        assert(self.imm_param['predict']!=-2 ** (64 - 1) and self.imm_param['predict']!=2 ** (64 - 1) - 1)
                        false_predict_param = random.randint(-2 ** (64 - 1), self.imm_param['predict'])
                        true_predict_param = random.randint(self.imm_param['predict'], 2 ** (64 - 1))
                    case 'BLTU':
                        assert(self.imm_param['predict']!=0 and self.imm_param['predict']!=2**64-1)
                        false_predict_param = random.randint(self.imm_param['predict'], 2 ** 64)
                        true_predict_param = random.randint(0, self.imm_param['predict'])
                    case 'BGEU':
                        assert(self.imm_param['predict']!=0 and self.imm_param['predict']!=2**64-1)
                        false_predict_param = random.randint(0, self.imm_param['predict'])
                        true_predict_param = random.randint(self.imm_param['predict'], 2 ** 64)
                    case _:
                        raise f"Error: branch_kind {self.imm_param['branch_kind']} not implemented!"

                if self.predict_kind == 'branch_not_taken':
                    false_predict_param, true_predict_param = true_predict_param, false_predict_param
            case _:
                raise "Error: predict_kind not implemented!"
        return true_predict_param, false_predict_param
    
    def _gen_data_list(self, true_predict_param, true_offset_param, false_predict_param, false_offset_param):
        self.data_list.append(RawInstruction('train_param_table:'))
        for i in range(self.train_loop):
            self.data_list.append(RawInstruction(f'train_predict_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {false_predict_param}'))
            self.data_list.append(RawInstruction(f'train_offset_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {false_offset_param}'))
            self.data_list.append(RawInstruction(f'train_delay_value_{i}:'))
            self.data_list.append(RawInstruction(f".dword {self.imm_param['delay']}"))
        self.data_list.append(RawInstruction('victim_param_table:'))
        for i in range(self.victim_loop):
            self.data_list.append(RawInstruction(f'victim_predict_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {true_predict_param}'))
            self.data_list.append(RawInstruction(f'victim_offset_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {true_offset_param}'))

    def _gen_inst_list(self):
        for i in range(self.train_loop):
            table_width = 3
            self.inst_list.append(RawInstruction(f'la t0, train_{i}_end'))
            self.inst_list.append(RawInstruction('la t1, store_ra'))
            self.inst_list.append(RawInstruction('sd t0, 0(t1)'))
            self.inst_list.append(RawInstruction('la t0, train_param_table'))
            self.inst_list.append(RawInstruction(f'ld a0, {i*8*table_width}(t0)'))
            self.inst_list.append(RawInstruction(f'ld a1, {i*8*table_width+8}(t0)'))
            self.inst_list.append(RawInstruction(f"ld {self.imm_param['delay_reg'].lower()}, {i*8*table_width+16}(t0)"))
            self.inst_list.append(RawInstruction('INFO_VCTM_START'))
            self.inst_list.append(RawInstruction(f'j predict'))
            self.inst_list.append(RawInstruction(f'train_{i}_end:'))
            self.inst_list.append(RawInstruction('INFO_VCTM_END'))
        
        for i in range(self.victim_loop):
            table_width = 2
            self.inst_list.append(RawInstruction(f'la t0, victim_{i}_end'))
            self.inst_list.append(RawInstruction('la t1, store_ra'))
            self.inst_list.append(RawInstruction('sd t0, 0(t1)'))
            self.inst_list.append(RawInstruction('la t0, victim_param_table'))
            self.inst_list.append(RawInstruction(f'ld a0, {i*8*table_width}(t0)'))
            self.inst_list.append(RawInstruction(f'ld a1, {i*8*table_width+8}(t0)'))
            self.inst_list.append(RawInstruction('INFO_VCTM_START'))
            self.inst_list.append(RawInstruction(f'j delay'))
            self.inst_list.append(RawInstruction(f'victim_{i}_end:'))
            self.inst_list.append(RawInstruction('INFO_VCTM_END'))

    def gen_random(self):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self):
        true_predict_param, false_predict_param = self._gen_predict_param()
        false_offset_param = 0
        true_offset_param = "secret + LEAK_TARGET - trapoline"
        self._gen_data_list(true_predict_param, true_offset_param, false_predict_param, false_offset_param)
        self._gen_inst_list()
        
    

    



