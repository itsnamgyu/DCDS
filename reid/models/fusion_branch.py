from torch import nn
import torch
import torch.nn.functional as F
from torch.autograd import Variable
import pdb




def Dist_Comp(pg1, pg2, dotp):
    A = dotp
    A = A - torch.min(A) #############

    #############################################################################################################3
    b = A.data.clone().contiguous()
    b.requires_grad = False

    # making the diagonal zero
    z = -1 * torch.diag(b)
    kk = Variable(torch.diag(z), requires_grad=False)
    A = kk + A

    B_size = A.size(0)

    F_rank = Variable(torch.zeros(B_size, B_size).cuda())

    for i in range(0, B_size):
        v = torch.ones(B_size, 1)
        v[i] = 0
        ind = (v != 0).nonzero()

        ind = ind[:, 0]
        ind = ind.cuda()
        M = A[ind][:, ind]

        
        M2 = Variable(M.data.clone(), requires_grad=False)
        EE = torch.eig(M2)
        EE2 = EE[0]

        alpha = torch.max(EE2[:, 0])
        alpha = alpha + 0.0005
        # alpha = 0.9

        ident_M = torch.eye(B_size, B_size)
        ident_M[i, i] = 0

        ident_M = ident_M * float(alpha)
        ident_M = Variable(ident_M, requires_grad=False)
        A_2 = A - ident_M.cuda()

        A_2 = A_2 + alpha

        # A_2 = torch.mul(A_2, p_g_score).contiguous()
        # calling Replicator dynamics
        P_g_rank = Replicator(A_2)

        # P_g_rank = torch.exp(P_g_rank)

        # P_g_rank = (P_g_rank - torch.min(P_g_rank))/ (torch.max(P_g_rank) - torch.min(P_g_rank))
        P_g_rank = P_g_rank.view(1, -1)

        F_rank[i, :] = P_g_rank

    # instances_num = 8
    # num_id = B_size / instances_num
    # temp = []

    # rpKnn =
    # pg1=torch.abs(pg1)
    # F_rank = torch.mm(F_rank, p_g_score)
    # pg1 = torch.abs(pg1)

    F_rank_T = (0.3 - F_rank).contiguous()

    F_rank = (0.1 * ((F_rank).cuda()) * (0.9 * (pg1).cuda())).contiguous()
    F_rank2 = (0.1 * (((F_rank_T)).cuda()) * (0.9 * (pg2).cuda())).contiguous()

    # K_nn2 = Variable(K_nn2)
    # Fr = (torch.matmul(F_rank, K_nn2).cuda()).contiguous()  # each column corresponds to the id, and the row corresponds to the gallery image

    return F_rank, F_rank2
    # return F_list


def Replicator(A_2):
    l = A_2.size(0)
    x = torch.ones(l, 1) / l

    x = Variable(x, requires_grad=True).cpu()
    A_f = A_2.cpu()
    x = x.cpu()

    # x = x * (torch.mm(A_f, x))
    # x = x / torch.sum(x)

    toll = 0.0000001
    ero = 2 * toll + 1
    max_it = 5
    if max_it:
        # print(self.max_it)
        max_it = max_it
    else:
        max_it = float('inf')

    count = int(0)

    x_old = x.cpu()
    x_old = x_old.type(torch.FloatTensor)
    x = (x * (torch.matmul(A_f, x))).contiguous()

    xx = torch.norm(x, p=2, dim=0).detach()
    x = x.div(xx.expand_as(x))

    while ero > toll and count < max_it:
        x_old = x.cpu()
        x_old = x_old.type(torch.FloatTensor)
        x = (x * (torch.matmul(A_f, x))).contiguous()

        xx = torch.norm(x, p=2, dim=0).detach()
        x = x.div(xx.expand_as(x))

        ero = torch.norm(x - x_old)
        ero = float(ero)
        count = count + 1

    return x.cuda()


class VNetExtension(nn.Module):
    def __init__(self, instances_num=4, base_model=None, embed_model=None, alpha=0.1):
        super(VNetExtension, self).__init__()
        self.instances_num = instances_num
        self.alpha = alpha
        self.base = base_model  # Resnet50
        self.embed = embed_model  

        # self.l = batch_size

        for i in range(len(embed_model)):
            setattr(self, 'embed_' + str(i), embed_model[i])

    def forward(self, x, epoch):
        x = self.base(x)  # Resnet
        #x1, x2, x3 = self.base(x)  # Resnet

        #x=x3
        #x=torch.cat((x1,x2,x),1)# 3072 feature size
        N, C, H, W = x.size()
        gallery_x = x
        gallery_x = gallery_x.contiguous()
        # gallery_x = gallery_x.view(gallery_num, C, H, W)
        f_size= C
        count = C / (len(self.embed))
        # outputs = Variable(torch.zeros((gallery_x.size(0)*gallery_x.size(0)),2).cuda())
        outputs = []
        for j in range(len(self.embed)):

            # p_g_score = self.embed[j](probe_x[:, i * count:(i + 1) * count].contiguous(),  # take us to embedding.py
            #                         gallery_x[:, i * count:(i + 1) * count].contiguous(),
            #                         p2g=True, g2g=False)
            p_g_score, dotp = self.embed[j](gallery_x[:, j * count:(j + 1) * count].contiguous(),
                                            gallery_x[:, j * count:(j + 1) * count].contiguous(),
                                            p2g=False, g2g=True)
            ''' Uncomment this to run CDS on both negative and posetive class of the linear output

            for jk in range(2):
                pg1 = p_g_score[:,:,jk]
                outt=Dist_Comp(pg1)
                outt = outt.view(outt.size(0)*outt.size(0))
                outputs[:,jk] = outt
            ##'''
            pg1 = p_g_score[:, :, 1].contiguous()
            pg2 = p_g_score[:, :, 0].contiguous()

            if epoch >= 0:
                outt, outt2 = Dist_Comp(pg1, pg2, dotp)  # Dominant Sets
                outt = outt.view(outt.size(0) * outt.size(0), 1).contiguous()
                outt2 = outt2.view(outt2.size(0) * outt2.size(0), 1).contiguous()
                outt3 = torch.cat((outt2, outt), -1).contiguous()
                outt = outt3.view(outt.size(0), 2).contiguous()

                outputs.append(outt)
            else:
                outt = pg1.view(pg1.size(0) * pg1.size(0), 1).contiguous()
                outt2 = pg2.view(pg2.size(0) * pg2.size(0), 1).contiguous()
                outt3 = torch.cat((outt2, outt), -1).contiguous()
                outt = outt3.view(outt.size(0), 2).contiguous()

                outputs.append(outt)

        outputs = torch.cat(outputs, 0)

        return outputs